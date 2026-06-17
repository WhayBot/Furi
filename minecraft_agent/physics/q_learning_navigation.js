const fs = require('fs');
const path = require('path');

// Module-level singleton for Express server (survives reconnect)
let _expressServer = null;
let _activeNavInstance = null;

class QLearningNavigation {
    constructor(bot) {
        this.bot = bot;
        this.target = null;
        
        this.qTable = {};
        this.qTableFile = path.join(__dirname, '../q_table.json');
        
        // Q-Learning Hyperparameters
        this.alpha = 0.1; // Learning rate
        this.gamma = 0.9; // Discount factor
        this.epsilon = 1.0; // Exploration rate (starts at 100% random)
        this.epsilonDecay = 0.9995; // Very slow decay for long training
        this.minEpsilon = 0.1; // Never stop exploring completely
        
        this.actions = ["forward", "jump_forward", "left", "right", "back"];
        
        this.lastState = null;
        this.lastAction = null;
        this.lastPos = null;
        this.lastDistToTarget = null;
        
        this.stuckTimer = 0;
        this.finalTarget = null;
        this.lastDetourLog = 0;
        this._saving = false;
        
        this.loadQTable();
        
        // Register as active instance (for Express routes on reconnect)
        _activeNavInstance = this;
        
        if (!_expressServer) {
            this.setupTrainerServer();
        }
    }

    loadQTable() {
        if (fs.existsSync(this.qTableFile)) {
            try {
                this.qTable = JSON.parse(fs.readFileSync(this.qTableFile, 'utf8'));
                // Attempt to load epsilon from saved data if we want to resume
                if (this.qTable._metadata && this.qTable._metadata.epsilon) {
                    this.epsilon = this.qTable._metadata.epsilon;
                }
                
                // BUG-R2-12 Fix: Count states without _metadata (so it doesn't show -1 when empty)
                const stateCount = Object.keys(this.qTable).filter(k => k !== '_metadata').length;
                console.log(`[Q-Learning] Loaded existing Q-Table with ${stateCount} states. Current Epsilon: ${this.epsilon.toFixed(3)}`);
            } catch (err) {
                console.error("[Q-Learning] Failed to load Q-table, starting fresh.");
            }
        }
    }

    saveQTable() {
        if (this._saving) return;
        this._saving = true;
        this.qTable._metadata = { epsilon: this.epsilon };
        fs.writeFile(this.qTableFile, JSON.stringify(this.qTable), () => {
            this._saving = false;
        });
    }

    setupTrainerServer() {
        const express = require('express');
        const cors = require('cors');
        const app = express();
        
        app.use(cors());
        app.use(express.json());
        
        app.post('/teach', (req, res) => {
            const nav = _activeNavInstance;
            if (!nav) return res.status(503).send({ error: 'No active bot' });
            
            const { state, action } = req.body;
            if (state && action) {
                if (!nav.qTable[state]) {
                    nav.qTable[state] = { forward: 0, jump_forward: 0, left: 0, right: 0, back: 0, jump: 0 };
                }
                if (nav.qTable[state][action] === undefined) {
                    nav.qTable[state][action] = 0;
                }
                nav.qTable[state][action] = 100.0;
                nav.saveQTable();
                console.log(`[Telepathy] Learned human action: ${action} at state ${state}!`);
                res.status(200).send({ status: 'learned' });
            } else {
                res.status(400).send({ error: 'Missing state or action' });
            }
        });
        
        app.post('/teach-action', (req, res) => {
            const { type, target, tool } = req.body;
            if (type) {
                if (type === 'break_block') {
                    console.log(`[Cognitive Telepathy] Learned to break: ${target} using ${tool}`);
                } else if (type === 'use_item') {
                    console.log(`[Cognitive Telepathy] Learned to use item: ${target}`);
                }
                res.status(200).send({ status: 'cognitive_learned' });
            } else {
                res.status(400).send({ error: 'Missing cognitive action type' });
            }
        });
        
        _expressServer = app.listen(3000, () => {
            console.log('[Trainer] Telepathy Server running on http://localhost:3000');
        }).on('error', (err) => {
            console.error('[Trainer] Could not start Telepathy server:', err.message);
        });
    }

    setTarget(pos, reason = '') {
        if (pos) {
            // Only log if target changed significantly
            if (!this.finalTarget || pos.distanceTo(this.finalTarget) > 3) {
                const p = pos.floored();
                console.log(`[Nav] Destination: (${p.x}, ${p.y}, ${p.z})${reason ? ' - ' + reason : ''}`);
            }
            this.finalTarget = pos;
            
            if (!this.target) {
                this.target = pos;
                this.lastDistToTarget = this.bot.entity.position.distanceTo(pos);
                this.lastState = null;
                this.lastAction = null;
            }
        } else {
            if (this.finalTarget) {
                console.log('[Nav] Stopped, no destination.');
            }
            this.finalTarget = null;
            this.target = null;
            this.clearControls();
        }
    }

    /**
     * Smart Steering / Radar Scan
     * Scans 16 directions around Furi and picks the best walkable direction
     * that also aligns with the final target. This allows Furi to navigate
     * around 2-high walls without mineflayer-pathfinder.
     */
    updateSteering() {
        if (!this.finalTarget) {
            this.target = null;
            return;
        }
        
        const pos = this.bot.entity.position;
        const distToFinal = pos.distanceTo(this.finalTarget);
        
        // If close to final target, go directly (no need to scan)
        if (distToFinal < 4) {
            this.target = this.finalTarget;
            return;
        }
        
        // Check direct path for impassable obstacles (2-high walls)
        const targetYaw = Math.atan2(-(this.finalTarget.x - pos.x), -(this.finalTarget.z - pos.z));
        const dirX = -Math.sin(targetYaw);
        const dirZ = -Math.cos(targetYaw);
        
        const isSolid = (b) => b && b.boundingBox === 'block';
        
        let directBlocked = false;
        for (const dist of [1.5, 2.5]) {
            const cp = pos.offset(dirX * dist, 0, dirZ * dist);
            const feet = this.bot.blockAt(cp);
            const head = this.bot.blockAt(cp.offset(0, 1, 0));
            
            // Cliff check
            const drop1 = this.bot.blockAt(cp.offset(0, -1, 0));
            const drop2 = this.bot.blockAt(cp.offset(0, -2, 0));
            const drop3 = this.bot.blockAt(cp.offset(0, -3, 0));
            const isCliff = (!isSolid(drop1) && !isSolid(drop2) && !isSolid(drop3));

            if ((isSolid(feet) && isSolid(head)) || isCliff) {
                directBlocked = true;
                break;
            }
        }
        
        // If direct path is clear AND we're not stuck, go direct
        if (!directBlocked && this.stuckTimer < 8) {
            this.target = this.finalTarget;
            return;
        }
        
        // Scan 16 evenly-spaced directions around Furi
        const numDirs = 16;
        let bestScore = -Infinity;
        let bestAngle = targetYaw;
        
        for (let i = 0; i < numDirs; i++) {
            const angle = (i / numDirs) * Math.PI * 2;
            const dx = -Math.sin(angle);
            const dz = -Math.cos(angle);
            
            // Check walkability at 1.5 and 3 blocks ahead in this direction
            let walkScore = 0;
            for (const dist of [1.5, 3]) {
                const cp = pos.offset(dx * dist, 0, dz * dist);
                const feet = this.bot.blockAt(cp);
                const head = this.bot.blockAt(cp.offset(0, 1, 0));
                const below = this.bot.blockAt(cp.offset(0, -1, 0));
                
                const drop2 = this.bot.blockAt(cp.offset(0, -2, 0));
                const drop3 = this.bot.blockAt(cp.offset(0, -3, 0));
                const isCliff = (!isSolid(below) && !isSolid(drop2) && !isSolid(drop3));
                
                if (isSolid(feet) && isSolid(head)) {
                    walkScore -= 10; // 2-high wall: IMPASSABLE
                } else if (isSolid(feet) && !isSolid(head)) {
                    walkScore += 3;  // 1-high block: jumpable (Boosted to encourage jumping over walls)
                } else if (isCliff) {
                    walkScore -= 20; // Deep drop: DANGEROUS!
                } else if (!isSolid(below)) {
                    walkScore -= 2;  // Small drop
                } else {
                    walkScore += 3;  // Clear and walkable
                }
            }
            
            // How well does this direction align with the final target?
            let angleDiff = angle - targetYaw;
            while (angleDiff < -Math.PI) angleDiff += Math.PI * 2;
            while (angleDiff > Math.PI) angleDiff -= Math.PI * 2;
            const alignment = Math.cos(angleDiff); // 1.0 = toward target, -1.0 = away
            
            let stuckModifier = 1.0;
            if (this.stuckTimer > 8) {
                // If stuck, prioritize lateral/backward movements to find a way around
                stuckModifier = -1.0; 
            }

            const totalScore = (alignment * 5.0 * stuckModifier) + walkScore;
            
            if (totalScore > bestScore) {
                bestScore = totalScore;
                bestAngle = angle;
            }
        }
        
        // Set waypoint in the best direction
        const wpDist = Math.min(4, distToFinal);
        const newTarget = pos.offset(-Math.sin(bestAngle) * wpDist, 0, -Math.cos(bestAngle) * wpDist);
        
        // Reset distance tracking when waypoint changes to avoid false reward spikes
        if (!this.target || this.target.distanceTo(newTarget) > 2) {
            this.lastDistToTarget = pos.distanceTo(newTarget);
        }
        this.target = newTarget;
        
        // Log detour (throttled to every 5s to avoid spam)
        if (Date.now() - this.lastDetourLog > 5000) {
            console.log('[Nav] Detour: direct path blocked, finding alternative route...');
            this.lastDetourLog = Date.now();
        }
        
        // Reset stuck timer since we found a new path
        if (this.stuckTimer >= 8) {
            this.stuckTimer = 0;
        }
    }

    clearControls() {
        this.bot.setControlState('forward', false);
        this.bot.setControlState('back', false);
        this.bot.setControlState('left', false);
        this.bot.setControlState('right', false);
        this.bot.setControlState('jump', false);
        this.bot.setControlState('sprint', false);
    }

    executeAction(actionStr) {
        this.clearControls();
        
        // Always look at target if we have one (handled smoothly by CameraOscillator)
        // if (this.target) {
        //     const diff = this.target.minus(this.bot.entity.position);
        //     const yaw = Math.atan2(-diff.x, -diff.z);
        //     this.bot.look(yaw, 0, true);
        // }

        switch (actionStr) {
            case "forward":
                this.bot.setControlState('forward', true);
                break;
            case "jump_forward":
                this.bot.setControlState('forward', true);
                this.bot.setControlState('jump', true);
                break;
            case "left":
                this.bot.setControlState('left', true);
                break;
            case "right":
                this.bot.setControlState('right', true);
                break;
            case "back":
                this.bot.setControlState('back', true);
                break;
            case "jump":
                this.bot.setControlState('jump', true);
                break;
        }
    }

    getState() {
        const pos = this.bot.entity.position;
        
        // 1. Target Direction (Front, Back, Left, Right)
        let targetDir = "none";
        if (this.target) {
            const diff = this.target.minus(pos);
            const yawToTarget = Math.atan2(-diff.x, -diff.z);
            const currentYaw = this.bot.entity.yaw;
            let yawDiff = yawToTarget - currentYaw;
            
            // Normalize
            while (yawDiff < -Math.PI) yawDiff += Math.PI * 2;
            while (yawDiff > Math.PI) yawDiff -= Math.PI * 2;
            
            if (Math.abs(yawDiff) < Math.PI / 4) targetDir = "front";
            else if (Math.abs(yawDiff) > Math.PI * 0.75) targetDir = "back";
            else if (yawDiff > 0) targetDir = "left";
            else targetDir = "right";
        }
        
        // 2. Obstacles (1 block ahead)
        const yaw = this.bot.entity.yaw;
        const dirX = -Math.sin(yaw);
        const dirZ = -Math.cos(yaw);
        
        const block1 = this.bot.blockAt(pos.offset(dirX * 1.5, 0, dirZ * 1.5));
        const block1Head = this.bot.blockAt(pos.offset(dirX * 1.5, 1, dirZ * 1.5));
        const blockBelow = this.bot.blockAt(pos.offset(0, -0.5, 0));
        
        const isSolid = (b) => b && b.name !== 'air' && b.name !== 'water' && b.name !== 'grass' && b.name !== 'tall_grass';
        
        let obstacleType = "none";
        if (isSolid(block1) && isSolid(block1Head)) obstacleType = "wall_2high";
        else if (isSolid(block1)) obstacleType = "wall_1high";
        
        const isAirBelow = !isSolid(blockBelow);

        // 3. Is Stuck?
        let isStuck = false;
        if (this.lastPos && pos.distanceTo(this.lastPos) < 0.2) {
            this.stuckTimer++;
            if (this.stuckTimer > 5) isStuck = true;
        } else {
            this.stuckTimer = 0;
        }

        const isInWater = this.bot.entity.isInWater;
        return `${targetDir}_${obstacleType}_stuck${isStuck}_airBelow${isAirBelow}_inWater${isInWater}`;
    }

    getQValue(state, action) {
        if (!this.qTable[state]) {
            this.qTable[state] = {};
            for (const a of this.actions) {
                this.qTable[state][a] = 0.0;
            }
        }
        return this.qTable[state][action];
    }

    getMaxQ(state) {
        if (!this.qTable[state]) return 0.0;
        let maxQ = -Infinity;
        for (const a of this.actions) {
            if (this.qTable[state][a] > maxQ) {
                maxQ = this.qTable[state][a];
            }
        }
        return maxQ;
    }

    chooseAction(state) {
        if (Math.random() < this.epsilon) {
            // Explore
            return this.actions[Math.floor(Math.random() * this.actions.length)];
        } else {
            // Exploit
            let bestActions = [];
            let maxQ = -Infinity;
            
            for (const a of this.actions) {
                const q = this.getQValue(state, a);
                if (q > maxQ) {
                    maxQ = q;
                    bestActions = [a];
                } else if (q === maxQ) {
                    bestActions.push(a); // Tie breaker
                }
            }
            return bestActions[Math.floor(Math.random() * bestActions.length)];
        }
    }

    calculateReward() {
        if (!this.target) return 0;
        
        let reward = -0.1; // Small negative reward for every step (encourages speed)
        
        const pos = this.bot.entity.position;
        const currentDist = pos.distanceTo(this.target);
        
        if (currentDist < 1.5) {
            return 50; // Reached target!
        }
        
        if (this.lastDistToTarget) {
            if (currentDist < this.lastDistToTarget - 0.2) {
                reward += 10; // Moved significantly closer
            } else if (currentDist > this.lastDistToTarget + 0.2) {
                reward -= 10; // Moved further away
            }
        }
        
        if (this.stuckTimer > 5) {
            reward -= 5; // Penalty for being stuck
        }
        
        if (this.lastPos && pos.y < this.lastPos.y - 2.5) {
            reward -= 30; // Big penalty for falling
        }
        
        // Big penalty if we took damage (requires linking to entityHurt event, but we can do a simplified check here)
        // For now, we omit damage penalty inside this loop, but can be added in core.js
        
        return reward;
    }

    update() {
        // Smart Steering: redirect target around obstacles if needed
        this.updateSteering();
        
        if (!this.target) return;

        const pos = this.bot.entity.position;
        
        // 1. Observe current state
        const currentState = this.getState();
        
        // 2. Calculate Reward from LAST action
        if (this.lastState && this.lastAction) {
            const reward = this.calculateReward();
            
            // Q-Learning Equation
            const oldQ = this.getQValue(this.lastState, this.lastAction);
            const maxFutureQ = this.getMaxQ(currentState);
            
            const newQ = oldQ + this.alpha * (reward + this.gamma * maxFutureQ - oldQ);
            this.qTable[this.lastState][this.lastAction] = newQ;
        }
        
        // 3. Reached target check
        if (pos.distanceTo(this.target) < 1.5) {
            // If this was a detour waypoint and we haven't reached the final destination yet
            if (this.finalTarget && pos.distanceTo(this.finalTarget) > 3) {
                this.stuckTimer = 0;
                this.lastState = null;
                this.lastAction = null;
                return; // updateSteering will set the next waypoint on the next tick
            }
            
            console.log('[Nav] Destination reached!');
            this.clearControls();
            this.target = null;
            this.finalTarget = null;
            this.saveQTable();
            return;
        }

        // 4. Choose next action
        const action = this.chooseAction(currentState);
        
        // 5. Execute action
        this.executeAction(action);
        
        const isMovingForward = this.bot.controlState.forward || action === 'forward' || action === 'jump_forward';

        if (this.bot.entity.isCollidedHorizontally && isMovingForward && !this.bot.entity.isInWater) {
            const yaw = this.bot.entity.yaw;
            const blockInFront = this.bot.blockAt(pos.offset(-Math.sin(yaw), 0, -Math.cos(yaw)));
            const blockAbove = this.bot.blockAt(pos.offset(-Math.sin(yaw), 1, -Math.cos(yaw)));
            
            const isSolid = (b) => b && b.boundingBox === 'block';
            
            if (isSolid(blockInFront) && !isSolid(blockAbove)) {
                // INSTINCT: Auto-Jump on land (ONLY if 1 block high)
                this.bot.setControlState('jump', true);
                this.bot.setControlState('forward', true);
            } else if (isSolid(blockInFront) && isSolid(blockAbove)) {
                // 2-block wall, do not jump uselessly!
                this.bot.setControlState('jump', false);
            }
        }
        
        // Anti-fall instinct (Reflex)
        const blockBelowFront1 = this.bot.blockAt(pos.offset(-Math.sin(this.bot.entity.yaw), -1, -Math.cos(this.bot.entity.yaw)));
        const blockBelowFront2 = this.bot.blockAt(pos.offset(-Math.sin(this.bot.entity.yaw), -2, -Math.cos(this.bot.entity.yaw)));
        const blockBelowFront3 = this.bot.blockAt(pos.offset(-Math.sin(this.bot.entity.yaw), -3, -Math.cos(this.bot.entity.yaw)));
        const isSolidBelow = (b) => b && b.boundingBox === 'block';

        if (!isSolidBelow(blockBelowFront1) && !isSolidBelow(blockBelowFront2) && !isSolidBelow(blockBelowFront3)) {
            if (isMovingForward) {
                // Ravine detected! Sudden brake.
                this.bot.setControlState('forward', false);
                this.bot.setControlState('jump', false);
            }
        }
        
        // 6. Decay epsilon
        if (this.epsilon > this.minEpsilon) {
            this.epsilon *= this.epsilonDecay;
        }

        // 7. Update tracking
        this.lastState = currentState;
        this.lastAction = action;
        this.lastPos = pos.clone();
        this.lastDistToTarget = pos.distanceTo(this.target);
        
        // Periodically save the Q-Table so we don't lose progress if it crashes
        if (Math.random() < 0.05) { // 5% chance every tick (~ every few seconds)
            this.saveQTable();
        }
    }
}

module.exports = QLearningNavigation;
