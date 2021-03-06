#!/usr/bin/env python3
import os
import signal
import subprocess
import numpy as np

try:
    import vrep
except:
    print ('--------------------------------------------------------------')
    print ('[ROBOTENV] "vrep.py" could not be imported. This means very probably that')
    print ('either "vrep.py" or the remoteApi library could not be found.')
    print ('Make sure both are in the same folder as this file,')
    print ('or appropriately adjust the file "vrep.py"')
    print ('--------------------------------------------------------------')
    print ('')


def printlog(functionName, returnCode):
    if returnCode == vrep.simx_return_ok:
        print("[ROBOTENV] {} successful".format(functionName))
    else:
        print("[ROBOTENV] {} got error code: {}".format(functionName, returnCode))

# use with statement
# for example:
# with robotEnv() as robotenv1:
#     ###use robotenv1 here###


home_path = os.path.expanduser('~')


class RobotEnv():
    # tasks
    TASK_REACH_CUBE = 1
    TASK_PUSH_CUBE_TO_TARGET_POSITION = 2
    # portNb = 19998
    vrepPath = os.path.join(home_path, "V-REP_PRO_EDU_V3_4_0_Linux", "vrep.sh")
    # blade "/home/diego/V-REP_PRO_EDU_V3_4_0_Linux/vrep.sh"
    # doc lab : "/homes/dam416/V-REP_PRO_EDU_V3_3_1_64_Linux/vrep.sh"
    current_dir_path = os.path.dirname(os.path.realpath(__file__))  # directory of this .py file
    # scenePath = os.path.join(current_dir_path, "MicoRobot.ttt")
    scenePath = os.path.join(current_dir_path, "MicoRobot_last.ttt")
    # scenePath = os.path.join(current_dir_path, "mico_scene_vrep3-3-1.ttt")

    # initialize the environment
    def __init__(self,
                 task,
                 targetCubePosition,
                 rewards_normalizer=0.1,
                 rewards_decay_rate=5,
                 showGUI=True,
                 velocity=1,
                 nSJoints=6,
                 nAJoints=6,
                 portNb=19999,
                 initial_joint_positions=None,
                 sync_mode=True,
                 shaping_rewards=True,
                 ignore_cube_z=True,
                 ):
        # actions/states/reward/done
        self.task = task  # see tasks 1, 2 above
        self.nSJoints = nSJoints  # num of joints to include in state vector (starts at base)
        self.nAJoints = nAJoints  # num of actionable joints (starts at base)
        self.portNb = portNb
        self.shaping_rewards = shaping_rewards
        self.ignore_cube_z = ignore_cube_z

        self.observation_space_size = self.nSJoints + 3 + 3  # FOR NOW #8 # 6 joint angles, cube position and end effector position
        if ignore_cube_z:
            self.observation_space_size -= 1
        if self.task == self.TASK_PUSH_CUBE_TO_TARGET_POSITION:
            if targetCubePosition is None:
                self.targetCubePosition = (0.15, 0.35)
            else:
                self.targetCubePosition = targetCubePosition  # tuple (x,y) target position relative to robot base
        else:
            self.targetCubePosition = None

        self.action_space_size = 3 * self.nAJoints  # (+Vel, -Vel, 0) for 6 joints
        self.action_space = range(0, self.action_space_size)
        self.observation_space = np.zeros((1, self.observation_space_size))
        self.state = np.zeros((1, self.observation_space_size))
        self.reward = 0
        self.goalReached = False
        self.minDistance = 0.05  # 5 cm
        # v-rep
        self.vrepProcess = None
        self.clientID = None
        # handles
        self.jointHandles = [0] * self.nSJoints
        self.fingersH1 = 0
        self.fingersH2 = 0
        self.jointsCollectionHandle = 0
        self.distToGoalHandle = 0
        self.distanceToCube = None
        # self.goal_reward = 1  # reward given at goal
        self.jointVel = velocity
        self.showGUI = showGUI
        self.rewards_decay_rate = rewards_decay_rate  # =1/0.3, reward is close to zero for 5 x 0.3 = 1.5 m
        self.rewards_normalizer = rewards_normalizer
        self.sync_mode = sync_mode
        self.initial_joint_positions = initial_joint_positions

        self.test_task = False

    # 'with' statement (used to exit the v-rep simulation properly)
    def __enter__(self):
        print('[ROBOTENV] Starting environment...')

        sync_mode_str = 'TRUE' if self.sync_mode else 'FALSE'
        portNb_str = str(self.portNb)

        # launch v-rep
        vrep_cmd = [self.vrepPath, '-gREMOTEAPISERVERSERVICE_' + portNb_str + '_FALSE_' + sync_mode_str]
        if not self.showGUI:
            vrep_cmd.append('-h')  # headless mode
        vrep_cmd.append(self.scenePath)

        # headless mode via ssh
        #     vrep_cmd = "xvfb-run --auto-servernum --server-num=1 /homes/dam416/V-REP_PRO_EDU_V3_4_0_Linux/vrep.sh -h -s -q MicoRobot.ttt"
        # vrep_cmd = ['xvfb-run', '--auto-servernum', '--server-num=1', self.vrepPath, '-h', '-s', '-q', self.scenePath]
        # vrep_cmd = ['xvfb-run', '--auto-servernum', '--server-num=1', self.vrepPath, '-h', self.scenePath]
        print('[ROBOTENV] Launching V-REP...')
        # NOTE: do not use "stdout=subprocess.PIPE" below to buffer logs, causes deadlock at episode 464! (flushing the buffer may work... but buffering is not needed)
        self.vrepProcess = subprocess.Popen(vrep_cmd, shell=False, preexec_fn=os.setsid)
        # connect to V-Rep Remote Api Server
        vrep.simxFinish(-1)  # close all opened connections
        # Connect to V-REP
        print('[ROBOTENV] Connecting to V-REP...')
        counter = 0
        while True:
            self.clientID = vrep.simxStart('127.0.0.1', self.portNb, True, False, 5000, 0)
            if self.clientID != -1:
                break
            else:
                print("[ROBOTENV] Connection failed, retrying")
                counter += 1
                if counter == 10:
                    raise RuntimeError('[ROBOTENV] Connection to V-REP failed.')

        if self.clientID == -1:
            print('[ROBOTENV] Failed connecting to remote API server')
        else:
            print('[ROBOTENV] Connected to remote API server')

            # close model browser and hierarchy window
            vrep.simxSetBooleanParameter(self.clientID, vrep.sim_boolparam_browser_visible, False, vrep.simx_opmode_blocking)
            vrep.simxSetBooleanParameter(self.clientID, vrep.sim_boolparam_hierarchy_visible, False, vrep.simx_opmode_blocking)
            vrep.simxSetBooleanParameter(self.clientID, vrep.sim_boolparam_console_visible, False, vrep.simx_opmode_blocking)

            # load scene
            # time.sleep(5) # to avoid errors
            # returnCode = vrep.simxLoadScene(self.clientID, self.scenePath, 1, vrep.simx_opmode_oneshot_wait) # vrep.simx_opmode_blocking is recommended

            # # Start simulation
            # # vrep.simxSetIntegerSignal(self.clientID, 'dummy', 1, vrep.simx_opmode_blocking)
            # # time.sleep(5)  #to center window for recordings
            # if self.initial_joint_positions is not None:
            #     self.initializeJointPositions(self.initial_joint_positions)
            # self.startSimulation()
            # # returnCode = vrep.simxStartSimulation(self.clientID, vrep.simx_opmode_blocking)
            # # printlog('simxStartSimulation', returnCode)

            # get handles and start streaming distance to goal
            for i in range(0, self.nSJoints):
                returnCode, self.jointHandles[i] = vrep.simxGetObjectHandle(self.clientID, 'Mico_joint' + str(i + 1), vrep.simx_opmode_blocking)
            printlog('simxGetObjectHandle', returnCode)
            returnCode, self.fingersH1 = vrep.simxGetObjectHandle(self.clientID, 'MicoHand_fingers12_motor1', vrep.simx_opmode_blocking)
            returnCode, self.fingersH2 = vrep.simxGetObjectHandle(self.clientID, 'MicoHand_fingers12_motor2', vrep.simx_opmode_blocking)
            returnCode, self.goalCubeH = vrep.simxGetObjectHandle(self.clientID, 'GoalCube', vrep.simx_opmode_blocking)
            returnCode, self.targetCubePositionH = vrep.simxGetObjectHandle(self.clientID, 'GoalPosition', vrep.simx_opmode_blocking)
            returnCode, self.robotBaseH = vrep.simxGetObjectHandle(self.clientID, 'Mico_link1_visible', vrep.simx_opmode_blocking)
            returnCode, self.jointsCollectionHandle = vrep.simxGetCollectionHandle(self.clientID, "sixJoints#", vrep.simx_opmode_blocking)
            returnCode, self.distToGoalHandle = vrep.simxGetDistanceHandle(self.clientID, "distanceToGoal#", vrep.simx_opmode_blocking)
            returnCode, self.endEffectorH = vrep.simxGetObjectHandle(self.clientID, "DummyFinger#", vrep.simx_opmode_blocking)
            # returnCode, self.distanceToGoal = vrep.simxReadDistance(self.clientID, self.distToGoalHandle, vrep.simx_opmode_streaming) #start streaming
            # returnCode, _, _, floatData, _ = vrep.simxGetObjectGroupData(self.clientID, self.jointsCollectionHandle, 15, vrep.simx_opmode_streaming) #start streaming

            if self.targetCubePosition is not None:
                # hide goal position plane
                visibility_layer_param_ID = 10
                visible_layer = 1
                returnCode = vrep.simxSetObjectIntParameter(self.clientID, self.targetCubePositionH, visibility_layer_param_ID, visible_layer, vrep.simx_opmode_blocking)
                # print('simxSetObjectIntParameter return Code: ', returnCode)
                self.initializeGoalPosition()

            # Start simulation
            if self.initial_joint_positions is not None:
                self.initializeJointPositions()

            self.reset()

            # self.startSimulation()
            # # returnCode = vrep.simxStartSimulation(self.clientID, vrep.simx_opmode_blocking)
            # # printlog('simxStartSimulation', returnCode)

            # self.updateState()  # default initial state: 180 degrees (=pi radians) for all angles

            # check the state is valid
            # while True:
            #     self.updateState()
            #     print("\nstate: ", self.state)
            #     print("\nreward: ", self.reward)
            #     # wait for a state
            #     if (self.state.shape == (1,self.observation_space_size) and abs(self.reward) < 1E+5):
            #         print("sent reward3=", self.reward)
            #         break

            print('[ROBOTENV] Environment succesfully initialised, ready for simulations')
            # while vrep.simxGetConnectionId(self.clientID) != -1:
            #     ##########################EXECUTE ACTIONS AND UPDATE STATE HERE #################################
            #     time.sleep(0.1)
            #     #end of execution loop
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        print('[ROBOTENV] Closing environment...')
        # check simulation is running before stopping (ctrl+C to kill case)

        self.stop_if_needed()

        # returnCode, serverState = vrep.simxGetInMessageInfo(self.clientID, vrep.simx_headeroffset_server_state)
        # stopped = not (serverState & 1)
        # if not stopped:
        #     # stop simulation
        #     returnCode = vrep.simxStopSimulation(self.clientID, vrep.simx_opmode_blocking)
        #     printlog('simxStopSimulation', returnCode)

        # # wait for simulation to stop
        # while True:
        #     returnCode, ping = vrep.simxGetPingTime(self.clientID)
        #     returnCode, serverState = vrep.simxGetInMessageInfo(self.clientID, vrep.simx_headeroffset_server_state)
        #     stopped = not (serverState & 1)
        #     if stopped:
        #         print("[ROBOTENV] Simulation stopped.")
        #         break

        # close the scene
        # returnCode = vrep.simxCloseScene(self.clientID,vrep.simx_opmode_blocking)

        # close v-rep
        vrep.simxFinish(self.clientID)
        # self.vrepProcess.terminate() #doesnt work
        os.killpg(os.getpgid(self.vrepProcess.pid), signal.SIGTERM)
        print('[ROBOTENV] Environment successfully closed')

    # reset the state for each new episode
    def reset(self):
        if vrep.simxGetConnectionId(self.clientID) != -1:
            # activate to change position at each env.reset()
            self.stop_if_needed()
            # if self.initial_joint_positions is not None:
            #     self.initializeJointPositions(self.initial_joint_positions)
            if self.test_task:
                self.initializeJointPositions()
            self.startSimulation()

            # get new measurements
            self.goalReached = False
            self.updateState()

            # check the state is valid
            # while True:
            #     self.updateState()
            #     # wait for a state
            #     if (self.state.shape == (1,self.observation_space_size) and abs(self.reward) < 1E+5):
            #         break
            return self.state

    def toggle_test_conditions(self, testing_policy):
        self.test_task = testing_policy

    def stop_if_needed(self):
        try_count = 0
        while True:
            try_count += 1
            vrep.simxSetIntegerSignal(self.clientID, 'dummySignal', 1, vrep.simx_opmode_blocking)

            # returnCode, ping = vrep.simxGetPingTime(self.clientID)
            returnCode, serverState = vrep.simxGetInMessageInfo(self.clientID, vrep.simx_headeroffset_server_state)
            # printlog('\nsimxGetInMessageInfo', returnCode)
            # print('\nServer state: ', serverState)
            # NOTE: if synchronous mode is needed:
            # check http://www.forum.coppeliarobotics.com/viewtopic.php?f=5&t=6603&sid=7939343e5e04b699af2d46f8d6efe7ba
            stopped = not (serverState & 1)
            if stopped:
                if try_count == 1:
                    print("[ROBOTENV] Simulation is already stopped.")
                else:
                    print("[ROBOTENV] Simulation stopped.")
                break
            else:
                if try_count == 1:
                    print('[ROBOTENV] Stopping simulation...')
                    returnCode = vrep.simxStopSimulation(self.clientID, vrep.simx_opmode_blocking)
                    if returnCode != vrep.simx_return_ok:
                        print("[ROBOTENV] simxStopSimulation failed, error code:", returnCode)

    def startSimulation(self):
        # make sure simulation is stopped, stop if needed
        self.stop_if_needed()
        vrep.simxSynchronous(self.clientID, self.sync_mode)
        vrep.simxStartSimulation(self.clientID, vrep.simx_opmode_blocking)
        # while returnCode != vrep.simx_return_ok:
        #     returnCode = vrep.simxStartSimulation(self.clientID, vrep.simx_opmode_blocking)

    def distance2reward(self, distance, decay_rate):
        if self.shaping_rewards:
            reward = self.rewards_normalizer * np.exp(-decay_rate * distance)
        else:
            # sparse rewards
            if distance < self.minDistance:
                reward = self.rewards_normalizer
            else:
                reward = 0.0
        return reward

    # update the state
    def updateState(self, centerInZeroRad=False):
        if vrep.simxGetConnectionId(self.clientID) != -1:
            jointPositions = self.getJointRawAngles()  # np.array
            jointPositions = jointPositions % (2 * np.pi)  # convert values to [0, 2*pi[

            if centerInZeroRad:
                newJPositions = [angle if angle <= np.pi else angle - 2 * np.pi for angle in jointPositions]  # convert values to ]-pi, +pi]
                newJPositions = np.array(newJPositions) + np.pi  # convert values to ]0, +2*pi]
            else:
                # center in pi
                newJPositions = np.array(jointPositions)

            # newJPositions2 = newJPositions / np.pi # previous version (mistake), convert to ]0, 2]
            newJPositions2 = newJPositions / (2 * np.pi)  # convert to ]0, 1]

            newJPositions3 = newJPositions2.reshape(6)
            # select the first relevant joints
            self.state = newJPositions3[0:self.nSJoints]

            returnCode, self.goalCubeRelPos = vrep.simxGetObjectPosition(self.clientID, self.goalCubeH, self.robotBaseH, vrep.simx_opmode_blocking)
            returnCode, self.endEffectorRelPos = vrep.simxGetObjectPosition(self.clientID, self.endEffectorH, self.robotBaseH, vrep.simx_opmode_blocking)
            if self.ignore_cube_z:
                self.goalCubeRelPos = (self.goalCubeRelPos[0], self.goalCubeRelPos[1])
            self.state = np.concatenate((self.state, self.endEffectorRelPos))
            self.state = np.concatenate((self.state, self.goalCubeRelPos))  # (x,y,z), z doesnt change in the plane

            returnCode, self.distanceToCube = vrep.simxReadDistance(self.clientID, self.distToGoalHandle, vrep.simx_opmode_blocking)  # dist in metres

            if self.task == self.TASK_REACH_CUBE:
                self.reward = self.distance2reward(self.distanceToCube, self.rewards_decay_rate)
                if self.distanceToCube < self.minDistance:
                    self.goalReached = True
                    print('[ROBOTENV] #### GOAL STATE ####')
            elif self.task == self.TASK_PUSH_CUBE_TO_TARGET_POSITION:
                self.distanceCubeTargetPos = np.sqrt((self.targetCubePosition[0] - self.goalCubeRelPos[0])**2 + (self.targetCubePosition[1] - self.goalCubeRelPos[1])**2)
                self.reward = self.distance2reward(self.distanceToCube, self.rewards_decay_rate) + self.distance2reward(self.distanceCubeTargetPos, 3 * self.rewards_decay_rate)
                if self.distanceCubeTargetPos < self.minDistance:
                    self.goalReached = True
                    print('[ROBOTENV] #### SUCCESS ####')
            else:
                raise RuntimeError('[ROBOTENV] Invalid Task')

    # execute action ACTIONS SHOULD BE THE RIGHT SIZE
    def step(self, actions):
        if vrep.simxGetConnectionId(self.clientID) != -1:
            # 6 * 3 = 18 actions -> action is in [0,17]
            # print("actions", actions)
            # jointNumber = action // 3
            if self.test_task:
                vel = 1.0
            else:
                vel = self.jointVel
            velMode = actions % 3 - 1  # speed to apply -1->-Vel;  0->zero;  +1->+Vel
            for i in range(0, self.nAJoints):
                vrep.simxSetJointTargetVelocity(self.clientID, self.jointHandles[i], velMode[i] * vel, vrep.simx_opmode_blocking)
            # hand actions
            # def openHand(self.clientID):
            #     closingVel = -0.04
            #     returnCode = vrep.simxSetJointTargetVelocity(self.clientID, fingersH1, -closingVel, vrep.simx_opmode_blocking)
            #     returnCode = vrep.simxSetJointTargetVelocity(self.clientID, fingersH2, -closingVel, vrep.simx_opmode_blocking)
            # def closeHand(self.clientID):
            #     closingVel = -0.04
            #     returnCode = vrep.simxSetJointTargetVelocity(self.clientID, fingersH1, closingVel, vrep.simx_opmode_blocking)
            #     returnCode = vrep.simxSetJointTargetVelocity(self.clientID, fingersH2, closingVel, vrep.simx_opmode_blocking)

            # simulation step
            vrep.simxSynchronousTrigger(self.clientID)
            vrep.simxGetPingTime(self.clientID)
            self.updateState()
            # check the state is valid
            # while True:
            #     self.updateState()
            #     # wait for a state
            #     if (self.state.shape == (1,self.observation_space_size) and abs(self.reward) < 1E+5):
            #         break
            return self.state, self.reward, self.goalReached

    # def initializeJointPositions(self, target_joint_positions):
    #     # targetPosInitial = np.array([1.0] * 6) * np.pi
    #     # targetPosStraight = np.array([0.66, 1.0, 1.25, 1.5, 1.0, 1.0]) * np.pi
    #     # targetPosHalfWayCube = np.array([0.66, 1.25, 1.25, 1.5, 1.0, 1.0]) * np.pi
    #     # targetPosNearCube = np.array([0.66, 1.5, 1.25, 1.5, 1.0, 1.0]) * np.pi
    #     self.enableControlLoop()
    #     for i in range(6):
    #         vrep.simxSetJointTargetPosition(self.clientID, self.jointHandles[i], target_joint_positions[i], vrep.simx_opmode_blocking)
    #     # wait to reach the target position
    #     maxDistance = 0.1
    #     sqMaxDistance = maxDistance ** 2
    #     while True:
    #         sqDistance = np.sum((self.getJointRawAngles() - target_joint_positions) ** 2)
    #         if sqDistance < sqMaxDistance:
    #             break
    #     self.disableControlLoop()

    def initializeJointPositions(self):
        # targetPosStraight = np.array([0.66, 1.0, 1.25, 1.5, 1.0, 1.0]) * np.pi
        # targetPosHalfWayCube = np.array([0.66, 1.25, 1.25, 1.5, 1.0, 1.0]) * np.pi
        # targetPosNearCube = np.array([0.66, 1.5, 1.25, 1.5, 1.0, 1.0]) * np.pi
        # enableControlLoop()
        if self.test_task:
            targetPos = np.array([1.0] * 6) * np.pi
        else:
            targetPos = self.initial_joint_positions

        for i in range(6):
            vrep.simxSetJointPosition(self.clientID, self.jointHandles[i], targetPos[i], vrep.simx_opmode_blocking)
            vrep.simxSetJointTargetPosition(self.clientID, self.jointHandles[i], targetPos[i], vrep.simx_opmode_blocking)
        # check joint positions
        # maxDistance = 0.05
        # while True:
        #     sqDistance = np.sum((self.getJointRawAngles() - self.initial_joint_positions) ** 2)
        #     if sqDistance < maxDistance ** 2:
        #         break
        # disableControlLoop()

    def initializeGoalPosition(self):
            returnCode, basePosition = vrep.simxGetObjectPosition(self.clientID, self.robotBaseH, -1, vrep.simx_opmode_blocking)
            targetCubePosition3D = (self.targetCubePosition[0], self.targetCubePosition[1], -basePosition[2] + 1e-3)
            vrep.simxSetObjectPosition(self.clientID, self.targetCubePositionH, self.robotBaseH, targetCubePosition3D, vrep.simx_opmode_blocking)

    def enableControlLoop(self):
        for i in range(6):
            vrep.simxSetObjectIntParameter(self.clientID, self.jointHandles[i], vrep.sim_jointintparam_ctrl_enabled, 1, vrep.simx_opmode_blocking)

    def disableControlLoop(self):
        for i in range(6):
            vrep.simxSetObjectIntParameter(self.clientID, self.jointHandles[i], vrep.sim_jointintparam_ctrl_enabled, 0, vrep.simx_opmode_blocking)

    def getJointRawAngles(self):
        # NOTE: default initial state: 180 degrees (=pi radians) for all angles
        # update joint angles, normalize to ]0,1]
        returnCode, _, _, floatData, _ = vrep.simxGetObjectGroupData(self.clientID, self.jointsCollectionHandle, 15, vrep.simx_opmode_blocking)  # or simx_opmode_blocking (not recommended)
        jointPositions = np.array(floatData[0::2])  # take elements at odd positions (even correspond to torques)
        return jointPositions
