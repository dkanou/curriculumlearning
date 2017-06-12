
# Lua implementation example
# vel=35
# accel=10
# jerk=5
# currentVel={0,0,0,0,0,0}
# currentAccel={0,0,0,0,0,0}
# maxVel={vel*math.pi/180,vel*math.pi/180,vel*math.pi/180,vel*math.pi/180,vel*math.pi/180,vel*math.pi/180}
# maxAccel={accel*math.pi/180,accel*math.pi/180,accel*math.pi/180,accel*math.pi/180,accel*math.pi/180,accel*math.pi/180}
# maxJerk={jerk*math.pi/180,jerk*math.pi/180,jerk*math.pi/180,jerk*math.pi/180,jerk*math.pi/180,jerk*math.pi/180}
# targetVel={0,0,0,0,0,0}

# targetPos1={90*math.pi/180,90*math.pi/180,90*math.pi/180,90*math.pi/180,90*math.pi/180,90*math.pi/180}
# simRMLMoveToJointPositions(jointHandles,-1,currentVel,currentAccel,maxVel,maxAccel,maxJerk,targetPos1,targetVel,{1,0,0,-1,-1,-1})

# targetPos2={90*math.pi/180,135*math.pi/180,225*math.pi/180,180*math.pi/180,180*math.pi/180,350*math.pi/180}
# simRMLMoveToJointPositions(jointHandles,-1,currentVel,currentAccel,maxVel,maxAccel,maxJerk,targetPos2,targetVel,{0,0,0,1,1,1})

# targetPos3={math.pi,math.pi,math.pi,math.pi,math.pi,math.pi}
# simRMLMoveToJointPositions(jointHandles,-1,currentVel,currentAccel,maxVel,maxAccel,maxJerk,targetPos3,targetVel,{-1,0,0,1,1,1})




# connect to V-Rep Remote Api Server
# clientID=vrep.simxStart(..........)

# Start simulation
# vrep.simxStartSimulation(clientID,vrep.simx_opmode_blocking)






import vrep
import sys
import time
import readchar

print('Mico Arm Program started')


#Arm
pi = 3.1416
portNb = 0
jointHandles = [0]*6

vel = 35
accel = 10
jerk = 5

currentVel = [0] * 6
currentAccel = [0] * 6
maxVel = [vel*pi/180] * 6
maxAccel = [accel*pi/180] * 6
maxJerk = [jerk*pi/180] * 6
targetVel = [0] * 6

targetPos1 = [90*pi/180] * 6
targetPos2 = [90*pi/180, 135*pi/180, 225*pi/180, 180*pi/180, 180*pi/180,350*pi/180]
targetPos3 = [pi] * 6
targetPos4 = [pi, 135*pi/180, 225*pi/180, 180*pi/180, 180*pi/180, 350*pi/180]

#Hand
closingVel = -0.04
# if (not closing) then
#     simSetJointTargetVelocity(j0,-closingVel)
#     simSetJointTargetVelocity(j1,-closingVel)
# else
#     simSetJointTargetVelocity(j0,closingVel)
#     simSetJointTargetVelocity(j1,closingVel)
# end

#testing setTargetVelocity
tVel = 2.0

if len(sys.argv) >= 10:
    portNb = int(sys.argv[1])
    jointHandles = list(map(int,sys.argv[2:8]))
    fingersH1 = int(sys.argv[8])
    fingersH2 = int(sys.argv[9])
else:
    print("Indicate following arguments: 'portNumber jointHandles'")
    time.sleep(5.0)
    sys.exit(0)

def openHand(clientID):
    errorCode = vrep.simxSetJointTargetVelocity(clientID, fingersH1, -closingVel, vrep.simx_opmode_oneshot)
    errorCode = vrep.simxSetJointTargetVelocity(clientID, fingersH2, -closingVel, vrep.simx_opmode_oneshot)

def closeHand(clientID):
    errorCode = vrep.simxSetJointTargetVelocity(clientID, fingersH1, closingVel, vrep.simx_opmode_oneshot)
    errorCode = vrep.simxSetJointTargetVelocity(clientID, fingersH2, closingVel, vrep.simx_opmode_oneshot)

def setJointTargetPositions(clientID, targetPositions):
    for i in range(6):
        errorCode = vrep.simxSetJointTargetPosition(clientID, jointHandles[i], targetPositions[i], vrep.simx_opmode_oneshot)
        if errorCode != vrep.simx_return_ok:
            print("SetJointTargetPosition got error code: %s" % errorCode)


vrep.simxFinish(-1)# close all opened connections
clientID = vrep.simxStart('127.0.0.1', portNb, True, True, 2000, 5)
if clientID != -1:
    print('Connected to remote API server')
    while vrep.simxGetConnectionId(clientID) != -1:
        # closeHand(clientID)
        # setJointTargetPositions(clientID, targetPos1)
        # errorCode = vrep.simxSetJointTargetVelocity(clientID, jointHandles[0], tVel, vrep.simx_opmode_blocking)
        # if errorCode != vrep.simx_return_ok:
        #     print("SetJointTargetVelocity got error code: %s" % errorCode)
        # time.sleep(2.0) #in sec

        # openHand(clientID)
        # setJointTargetPositions(clientID, targetPos2)
        # time.sleep(2.0) #in sec

        # closeHand(clientID)
        # setJointTargetPositions(clientID, targetPos3)
        # time.sleep(2.0) #in sec

        # testing settargetvel with arrow pressing
        c = readchar.readchar()
        if c == 'a':    
            return_code = vrep.simxSetJointTargetVelocity(clientID, jointHandles[5], tVel, vrep.simx_opmode_blocking)
            if errorCode != vrep.simx_return_ok:
                print("SetJointTargetPosition got error code: %s" % errorCode)
        elif c == 'd':
            errorCode = vrep.simxSetJointTargetVelocity(clientID, jointHandles[5], -tVel, vrep.simx_opmode_blocking)
            if errorCode != vrep.simx_return_ok:
                print("SetJointTargetPosition got error code: %s" % errorCode)
        elif c == 's':
            errorCode = vrep.simxSetJointTargetVelocity(clientID, jointHandles[5], 0, vrep.simx_opmode_blocking)
            if errorCode != vrep.simx_return_ok:
                print("SetJointTargetPosition got error code: %s" % errorCode)
        print('char=',c)       # --> gives me "0"
        time.sleep(0.1)

    vrep.simxFinish(clientID)
else:
    print('Failed connecting to remote API server')

print('Mico Arm Program ended')


### send string signal to execute setTargetPositions in the server side

# #pack lists of int lists into a single string
# def pack2DIntArray(intLists):
#     stringData = ""
#     for intList in intLists:
#         stringData += vrep.simxPackInts(intList)
#     return stringData

# #pack lists of float lists into a single string
# def pack2DFloatArray(floatLists):
#     stringData = ""
#     for floatList in floatLists:
#         stringData += vrep.simxPackInts(floatList)
#     return stringData

# intLists = jointHandles
# floatLists = [currentVel, currentAccel, maxVel, maxAccel, maxJerk, targetPos, targetVel]
# stringData = pack2DIntArray(intLists)+pack2DFloatArray(floatLists)
# vrep.simxSetStringSignal(clientID, "moveToPosition", stringData, vrep.simx_opmode_oneshot_wait)

# while True:
#     returnCode, signalValue = vrep.simxGetStringSignal(clientID, "moveToPosition", vrep.simx_opmode_oneshot_wait)

# explore simxCallScriptFunction to call v-rep Lua script functions?