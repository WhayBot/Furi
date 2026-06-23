require('dotenv').config();
const mineflayer = require('mineflayer');
const fs = require('fs');
const path = require('path');
const vec3 = require('vec3');

const TARGET_PLAYER = process.env.TRAINER_TARGET_PLAYER || "YourUsernameHere";
const qTableFile = path.join(__dirname, 'q_table.json');
let _saving = false;

console.log(`[Trainer] Starting CCTV Bot to monitor player: ${TARGET_PLAYER}`);

const bot = mineflayer.createBot({
    host: process.env.MC_HOST,
    port: parseInt(process.env.MC_PORT),
    username: "CCTV_Bot",
    version: process.env.MC_VERSION
});

let qTable = {};
if (fs.existsSync(qTableFile)) {
    qTable = JSON.parse(fs.readFileSync(qTableFile, 'utf8'));
}

let lastPos = null;

bot.on('spawn', () => {
    console.log('[Trainer] CCTV Bot successfully joined! Waiting for target...');
    
    setInterval(() => {
        const target = bot.players[TARGET_PLAYER]?.entity;
        if (!target) return; 

        const currentPos = target.position.clone();
        
        if (lastPos) {
            const delta = currentPos.minus(lastPos);
            
            if (Math.abs(delta.x) > 0.01 || Math.abs(delta.z) > 0.01 || delta.y > 0) {
                
                let action = "none";
                const isJumping = delta.y > 0.1; 
                
                if (isJumping && (Math.abs(delta.x) > 0 || Math.abs(delta.z) > 0)) {
                    action = "jump_forward";
                } else if (isJumping) {
                    action = "jump";
                } else if (Math.abs(delta.x) > 0 || Math.abs(delta.z) > 0) {
                    action = "forward";
                }
                
                if (action !== "none") {
                    const yaw = target.yaw;
                    const forwardVector = vec3(-Math.sin(yaw), 0, -Math.cos(yaw)).normalize();
                    
                    const frontPos = currentPos.offset(forwardVector.x, 0, forwardVector.z).floored();
                    const blockFront1 = bot.blockAt(frontPos);
                    const blockFront2 = bot.blockAt(frontPos.offset(0, 1, 0));
                    const blockBelow = bot.blockAt(currentPos.offset(0, -0.5, 0).floored());

                    const front1 = blockFront1 && blockFront1.boundingBox === 'block';
                    const front2 = blockFront2 && blockFront2.boundingBox === 'block';
                    const isAirBelow = !blockBelow || blockBelow.boundingBox === 'empty';
                    const isStuck = target.velocity.x === 0 && target.velocity.z === 0 && (front1 || front2);
                    const inWater = target.isInWater || false;

                    let frontType = "none";
                    if (front1 && front2) frontType = "wall_2high";
                    else if (front1) frontType = "wall_1high";

                    let targetDir = "front";
                    if (action === 'back') targetDir = "back";
                    else if (action === 'left') targetDir = "left";
                    else if (action === 'right') targetDir = "right";

                    const stateStr = `${targetDir}_${frontType}_stuck${isStuck}_airBelow${isAirBelow}_inWater${inWater}`;

                    if (!qTable[stateStr]) {
                        qTable[stateStr] = { forward: 0, jump_forward: 0, left: 0, right: 0, back: 0, jump: 0 };
                    }
                    if (qTable[stateStr][action] === undefined) qTable[stateStr][action] = 0;
                    
                    qTable[stateStr][action] = 100.0;
                    if (!_saving) {
                        _saving = true;
                        fs.writeFile(qTableFile, JSON.stringify(qTable), () => { _saving = false; });
                    }
                    
                    console.log(`[CCTV] You performed: ${action} in state ${stateStr} -> Memory saved!`);
                }
            }
        }
        
        lastPos = currentPos;
    }, 100);
});

bot.on('error', err => console.log('[Trainer Error]', err.message));
bot.on('end', () => console.log('[Trainer] Disconnected.'));
