// This file is unused, idk why i push this
// Please just move on to the next file

const vec3 = require('vec3');
const SteeringNavigation = require('./physics/steering_navigation');
const CameraOscillator = require('./physics/camera_oscillator');
const GaussianAim = require('./combat/gaussian_aim');
const FoveatedVision = require('./perception/foveated_vision');
const UtilityDecision = require('./brain/utility_decision');

console.log("=== VIRTUAL PHYSICS SIMULATION ===");

class MockBot {
    constructor() {
        this.entity = { position: vec3(0, 0, 0), yaw: 0, pitch: 0, isCollidedHorizontally: false };
    }
    look(yaw, pitch, force) {
        this.entity.yaw = yaw;
        this.entity.pitch = pitch;
    }
    clearControlStates() {}
    setControlState(state, val) {}
}

const mockBot = new MockBot();

console.log("\n[1] Testing Camera Oscillator (Panic Mode = Underdamped)");
const cam = new CameraOscillator(mockBot);
cam.setPanicMode(true); 
cam.setTargetYaw(Math.PI / 2); // 90 degrees target (approx 1.57)

let outputOscillator = "";
for(let i=0; i<10; i++) {
    cam.update(0.05); // 50ms tick
    outputOscillator += `Tick ${i}: yaw = ${cam.currentYaw.toFixed(4)} | vel = ${cam.velocityYaw.toFixed(4)}\n`;
}
console.log("Target Yaw: ~1.5708");
console.log(outputOscillator);

console.log("\n[2] Testing Reynolds Steering Behavior");
const steering = new SteeringNavigation(mockBot);
mockBot.cameraOscillator = cam;
mockBot.entity.position = vec3(0, 0, 0);
steering.setTarget(vec3(5, 0, 5));

let outputSteering = "";
for(let i=0; i<5; i++) {
    steering.update();
    outputSteering += `Tick ${i}: pos=(${mockBot.entity.position.x.toFixed(4)}, ${mockBot.entity.position.z.toFixed(4)}) vel=(${steering.currentVelocity.x.toFixed(4)}, ${steering.currentVelocity.z.toFixed(4)})\n`;
    mockBot.entity.position.x += steering.currentVelocity.x * 0.05;
    mockBot.entity.position.z += steering.currentVelocity.z * 0.05;
}
console.log(outputSteering);

console.log("\n[3] Testing Gaussian Aim (Fitts's Law)");
const aim = new GaussianAim();
const targetPos = vec3(10, 10, 10);
const panicLevel = 2.0;
const mouseVel = Math.abs(cam.velocityYaw);
const stdDev = aim.calculateErrorStdDev(mouseVel, panicLevel);
const errTarget = aim.applyAimError(targetPos, mouseVel, panicLevel);
console.log(`Mouse Velocity: ${mouseVel.toFixed(4)}`);
console.log(`Std Dev: ${stdDev.toFixed(4)}`);
console.log(`Original Target: (${targetPos.x}, ${targetPos.y}, ${targetPos.z})`);
console.log(`Errored Target:  (${errTarget.x.toFixed(4)}, ${errTarget.y.toFixed(4)}, ${errTarget.z.toFixed(4)})`);

console.log("\n[4] Testing Continuous Utility Function");
mockBot.food = 6; 
mockBot.health = 20; 
const utility = new UtilityDecision(mockBot);
console.log(`State -> Food: ${mockBot.food}, Health: ${mockBot.health}`);
console.log(`Best Action: ${utility.evaluate()}`);

mockBot.food = 20; 
mockBot.health = 4; 
console.log(`State -> Food: ${mockBot.food}, Health: ${mockBot.health}`);
console.log(`Best Action: ${utility.evaluate()}`);
