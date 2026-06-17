const mineflayer = require('mineflayer');
const QLearningNavigation = require('./physics/q_learning_navigation');
const CameraOscillator = require('./physics/camera_oscillator');
const GaussianAim = require('./combat/gaussian_aim');
const FoveatedVision = require('./perception/foveated_vision');
const UtilityDecision = require('./brain/utility_decision');
const GroqBrain = require('./groq_brain');
const InventoryManager = require('./survival/inventory_manager');
const SurvivalInstincts = require('./survival/survival_instincts');
const CropFarmer = require('./survival/crop_farmer');
const BlockInteraction = require('./interaction/block_interaction');

const vec3 = require('vec3');
const Memory = require('./brain/memory');

class MinecraftAgent {
    constructor(options) {
        this.bot = mineflayer.createBot(options);
        this.steering = new QLearningNavigation(this.bot);
        this.camera = new CameraOscillator(this.bot);
        this.bot.cameraOscillator = this.camera; 

        this.aim = new GaussianAim();
        this.vision = new FoveatedVision(this.bot);

        // Hostile mob list (shared across all modules)
        this.hostiles = ['zombie', 'skeleton', 'creeper', 'spider', 'husk', 'drowned', 'enderman'];

        this.utility = new UtilityDecision(this.bot, this.hostiles);
        
        const groqKeys = [
            process.env.GROQ_API_KEY,
            process.env.GROQ_API_KEY_2,
            process.env.GROQ_API_KEY_3
        ].filter(Boolean);

        this.groq = new GroqBrain(groqKeys.length > 0 ? groqKeys : ["dummy_key"]);
        this.memory = new Memory();
        this.inventoryManager = new InventoryManager(this.bot);
        this.cropFarmer = new CropFarmer(this.bot, this.steering, this.inventoryManager, this.memory);
        this.survivalInstincts = new SurvivalInstincts(this.bot, this.inventoryManager, this.memory, this.cropFarmer);
        this.blockInteraction = new BlockInteraction(this.bot, this.inventoryManager, this.memory);
        this.userDirective = "Survive and thrive";

        this.macroAction = 'EXPLORE';
        this.squidFascinationTimer = 0;
        this.intervalIds = [];


        this.followTarget = null;
        this.followLastKnownPos = null;
        this.followStartTime = null;
        this.followMaxDuration = 5 * 60 * 1000;

        this.setupEventLoggers();
        this.setupChatListener();

        this.bot.on('spawn', () => {
            console.log('[System] Bot spawned. Starting Dual-Loop Architecture...');
            
            if (!this.loopsStarted) {
                this.startGameTickLoop();
                this.startCognitiveLoop();
                this.startSurvivalLoop();
                this.startMacroLoop();
                this.loopsStarted = true;
                
                console.log('[Cognitive] Survival Instincts ENABLED (auto-eat, anti-drowning, auto-weapon)');
                console.log(`[Cognitive] Inventory: ${this.inventoryManager.getInventorySummary()}`);
            }
        });
    }

    setupEventLoggers() {
        this.bot.on('death', async () => {
            this.memory.logEvent("Bot died.");
            console.log("💀 Bot died! Initiating Death Reflection...");
            const lesson = await this.groq.reflectOnDeath(this.memory.getRecentEvents());
            if (lesson) {
                console.log(`💡 Lesson learned: ${lesson}`);
                this.memory.addLifeLesson(lesson);
            }
        });

        this.bot.on('entityHurt', (entity) => {
            if (entity === this.bot.entity) {
                this.memory.logEvent(`Bot took damage. Health is now ${this.bot.health}`);
            }
        });
        
        this.bot.on('itemDrop', (entity) => {
            if (Math.random() < 0.1) {
                this.memory.logEvent("Bot saw an item drop nearby.");
            }
        });
    }

    setupChatListener() {
        this.bot.on('chat', (username, message) => {
            if (username === this.bot.username) return;

            const msg = message.toLowerCase().trim();

            if (msg.includes('furi') && (msg.includes('ikut') || msg.includes('follow'))) {
                if (this.followTarget && this.followTarget !== username) {
                    console.log(`[Chat] ${username} requested follow, but already following ${this.followTarget}. Ignored.`);
                    return;
                }

                this.followTarget = username;
                this.followLastKnownPos = null;
                this.followStartTime = Date.now();
                console.log(`[Chat] ${username} requested follow. FOLLOW MODE ENABLED.`);
                return;
            }

            if (this.followTarget && username === this.followTarget) {
                if (msg.includes('berhenti') || msg.includes('stop') || msg.includes('diam')) {
                    console.log(`[Chat] ${username} requested stop. FOLLOW MODE DISABLED.`);
                    this.followTarget = null;
                    this.followLastKnownPos = null;
                    this.followStartTime = null;
                    this.steering.setTarget(null);
                    return;
                }
            }
        });

        this.bot.on('playerLeft', (player) => {
            if (this.followTarget && player.username === this.followTarget) {
                console.log(`[Chat] ${this.followTarget} left the server. FOLLOW MODE DISABLED.`);
                this.followTarget = null;
                this.followLastKnownPos = null;
                this.followStartTime = null;
                this.steering.setTarget(null);
            }
        });
    }

    startGameTickLoop() {
        // 20 Hz (50ms)
        const id = setInterval(() => {
            const isFarming = this.cropFarmer && this.cropFarmer.state !== 'IDLE';
            if (!this.survivalInstincts.isEating && !isFarming) {
                this.steering.update();
            }
            this.camera.update(0.05);
        }, 50);
        this.intervalIds.push(id);
    }

    startCognitiveLoop() {
        // 5 Hz (200ms)
        const id = setInterval(() => {
            if (this.cropFarmer && this.cropFarmer.state !== 'IDLE') {
                return;
            }

            if (this.followTarget) {
                this.processFollowMode();
                return;
            }

            const target = this.vision.getMostSalientTarget();
            const bestAction = this.utility.evaluate(target);
            
            if (this.squidFascinationTimer > 0) {
                this.squidFascinationTimer--;
                const squid = Object.values(this.bot.entities).find(e => e.name === 'squid' && e.position.distanceTo(this.bot.entity.position) < 25);
                if (squid) {
                    const pos = this.bot.entity.position.offset(0, 1.62, 0);
                    const tPos = squid.position.offset(0, squid.height/2 || 1, 0);
                    const diff = tPos.minus(pos);
                    const yaw = Math.atan2(-diff.x, -diff.z);
                    const pitch = Math.atan2(diff.y, Math.sqrt(diff.x * diff.x + diff.z * diff.z));
                    
                    this.camera.setTargetYaw(yaw);
                    this.camera.setTargetPitch(pitch);
                    this.steering.setTarget(squid.position, 'Fascinated by a squid');
                    return; // Skip normal target processing
                } else {
                    this.squidFascinationTimer = 0;
                }
            } else if (this.bot.entity.isInWater && Math.random() < 0.0000833) {
                const nearbySquid = Object.values(this.bot.entities).find(e => e.name === 'squid' && e.position.distanceTo(this.bot.entity.position) < 20);
                if (nearbySquid) {
                    this.squidFascinationTimer = 50;
                }
            }
            
            if (target) {
                const pos = this.bot.entity.position.offset(0, 1.62, 0);
                const tPos = target.position.offset(0, target.height/2 || 1, 0);
                
                const mouseVel = Math.abs(this.camera.velocityYaw) + Math.abs(this.camera.velocityPitch);
                const panic = (bestAction === 'flee') ? 2.0 : 1.0;
                
                const erroredTarget = this.aim.applyAimError(tPos, mouseVel, panic);
                
                const diff = erroredTarget.minus(pos);
                const yaw = Math.atan2(-diff.x, -diff.z);
                const groundDistance = Math.sqrt(diff.x * diff.x + diff.z * diff.z);
                const pitch = Math.atan2(diff.y, groundDistance);

                this.camera.setPanicMode(bestAction === 'flee');

                this.camera.setTargetYaw(yaw);
                this.camera.setTargetPitch(pitch);

                const nearbyHostile = Object.values(this.bot.entities).find(e => 
                    e.type === 'mob' && this.hostiles.includes(e.name) && e.position.distanceTo(this.bot.entity.position) < 3
                );
                if (nearbyHostile) {
                    this.survivalInstincts.ensureBestWeaponEquipped();
                    this.bot.attack(nearbyHostile);
                }

                if (bestAction === 'flee') {
                    const hostileToFlee = Object.values(this.bot.entities).find(e => 
                        e.type === 'mob' && this.hostiles.includes(e.name) && e.position.distanceTo(this.bot.entity.position) < 15
                    );
                    
                    if (hostileToFlee) {
                        const hPos = hostileToFlee.position.offset(0, hostileToFlee.height/2 || 1, 0);
                        const hDiff = pos.minus(hPos);
                        const hDist = Math.sqrt(hDiff.x * hDiff.x + hDiff.z * hDiff.z);
                        
                        const runDir = pos.minus(hPos).scaled(1 / (hDist || 1));
                        const strafeDir = vec3(-runDir.z, 0, runDir.x).scaled(Math.random() > 0.5 ? 1 : -1); 
                        
                        // Combine 70% backwards, 30% sideways
                        const escapeVector = runDir.scaled(0.7).plus(strafeDir.scaled(0.3)).scaled(5);
                        this.steering.setTarget(this.bot.entity.position.plus(escapeVector), 'Fleeing from ' + hostileToFlee.name);
                    } else {
                        this.steering.setTarget(target.position, 'Approaching ' + target.name);
                    }
                } else if (bestAction === 'fight') {
                    this.steering.setTarget(target.position, 'Attacking ' + target.name);
                    if (groundDistance < 3) {
                        this.bot.attack(target);
                    }
                } else {
                    this.steering.setTarget(target.position, 'Approaching ' + target.name);
                }
            } else {
                // No salient targets in FOV
                if (this.macroAction === 'EXPLORE' || this.macroAction === 'FLEE') {
                    this.camera.setTargetPitch(0);
                    
                    if (!this.steering.target) {
                        const randomDir = this.bot.entity.position.offset(
                            (Math.random() - 0.5) * 10,
                            0,
                            (Math.random() - 0.5) * 10
                        );
                        this.steering.setTarget(randomDir, 'Exploring new area');
                    } else {
                        const diff = this.steering.target.minus(this.bot.entity.position);
                        const yaw = Math.atan2(-diff.x, -diff.z);
                        this.camera.setTargetYaw(yaw);
                    }
                } else {
                    this.steering.setTarget(null);
                }
            }

        }, 200);
        this.intervalIds.push(id);
    }

    startSurvivalLoop() {
        // 1 Hz (1000ms)
        const id = setInterval(async () => {
            try {
                await this.survivalInstincts.update();
            } catch (e) {
                // Survival checks should never crash the bot
            }
        }, 1000);
        this.intervalIds.push(id);
    }

    startMacroLoop() {
        // 10s Macro
        const id = setInterval(async () => {
            const inventorySummary = this.inventoryManager.getInventorySummary();
            const nearbyInfo = this.scanNearbyBlocks();

            const state = {
                health: this.bot.health,
                hunger: this.bot.food,
                inventory: inventorySummary,
                nearby: nearbyInfo,
                recentEvents: this.memory.getRecentEvents(),
                lifeLessons: this.memory.getLifeLessons(),
                userDirective: this.userDirective
            };
            
            if (Math.random() < 0.3) {
                this.memory.logEvent(`Bot is at ${this.bot.entity.position.floored()}. Inventory: ${inventorySummary}`);
            }

            const decision = await this.groq.decideMacroStrategy(state);
            console.log(`[Groq Macro] Strategy: ${decision.strategy} | Action: ${decision.action}`);
            this.macroAction = decision.action;
        }, 10000);
        this.intervalIds.push(id);
    }

    /**
     * Scan notable blocks nearby for Groq's context
     */
    scanNearbyBlocks() {
        try {
            const pos = this.bot.entity.position;
            const found = {};
            const interestingBlocks = [
                'oak_log', 'spruce_log', 'birch_log', 'jungle_log', 'acacia_log', 'dark_oak_log',
                'coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore', 'copper_ore',
                'crafting_table', 'furnace', 'chest', 'water', 'lava',
            ];

            for (let dx = -8; dx <= 8; dx += 4) {
                for (let dz = -8; dz <= 8; dz += 4) {
                    for (let dy = -2; dy <= 4; dy += 2) {
                        const block = this.bot.blockAt(pos.offset(dx, dy, dz));
                        if (block && interestingBlocks.includes(block.name)) {
                            found[block.name] = (found[block.name] || 0) + 1;
                        }
                    }
                }
            }

            const entries = Object.entries(found);
            if (entries.length === 0) return 'Open terrain, no notable blocks nearby.';
            return entries.map(([name, count]) => `${name}(${count})`).join(', ');
        } catch (e) {
            return 'Unknown terrain';
        }
    }

    /**
     * Dynamic Path Recalculation for Follow Mode
     */
    processFollowMode() {
        if (this.followStartTime && (Date.now() - this.followStartTime) > this.followMaxDuration) {
            console.log(`[Follow] Timeout! Followed ${this.followTarget} for 5 minutes without reaching. Stopping.`);
            this.followTarget = null;
            this.followLastKnownPos = null;
            this.followStartTime = null;
            this.steering.setTarget(null);
            return;
        }

        const playerEntity = this.bot.players[this.followTarget]?.entity;

        if (!playerEntity) {
            if (!this.followLastKnownPos) {
                if (Math.random() < 0.01) {
                    console.log(`[Follow] Searching for ${this.followTarget}... (too far to see)`);
                }
            }
            return;
        }

        const playerPos = playerEntity.position;
        const furiPos = this.bot.entity.position;
        const distToPlayer = furiPos.distanceTo(playerPos);

        if (distToPlayer < 3) {
            this.steering.setTarget(null);
            this.followLastKnownPos = playerPos.clone();
            this.followStartTime = Date.now();

            const pos = furiPos.offset(0, 1.62, 0);
            const tPos = playerPos.offset(0, playerEntity.height / 2 || 1, 0);
            const diff = tPos.minus(pos);
            const yaw = Math.atan2(-diff.x, -diff.z);
            const pitch = Math.atan2(diff.y, Math.sqrt(diff.x * diff.x + diff.z * diff.z));
            this.camera.setTargetYaw(yaw);
            this.camera.setTargetPitch(pitch);
            return;
        }

        const needsRecalc =
            !this.followLastKnownPos ||
            !this.steering.finalTarget ||
            playerPos.distanceTo(this.followLastKnownPos) > 3 ||
            this.steering.stuckTimer > 8;

        if (needsRecalc) {
            this.followLastKnownPos = playerPos.clone();
            this.steering.setTarget(playerPos, `Following ${this.followTarget}`);
        }

        const pos = furiPos.offset(0, 1.62, 0);
        const tPos = playerPos.offset(0, playerEntity.height / 2 || 1, 0);
        const diff = tPos.minus(pos);
        const yaw = Math.atan2(-diff.x, -diff.z);
        const pitch = Math.atan2(diff.y, Math.sqrt(diff.x * diff.x + diff.z * diff.z));
        this.camera.setTargetYaw(yaw);
        this.camera.setTargetPitch(pitch);

        const nearbyHostile = Object.values(this.bot.entities).find(e =>
            e.type === 'mob' && this.hostiles.includes(e.name) && e.position.distanceTo(furiPos) < 3
        );
        if (nearbyHostile) {
            this.survivalInstincts.ensureBestWeaponEquipped();
            this.bot.attack(nearbyHostile);
        }
    }

    /**
     * Clears all interval loops
     */
    destroy() {
        for (const id of this.intervalIds) {
            clearInterval(id);
        }
        this.intervalIds = [];
        this.followTarget = null;
        this.followLastKnownPos = null;
        this.followStartTime = null;
        this.steering.clearControls();
        this.loopsStarted = false;
        console.log('[System] MinecraftAgent destroyed. All loops cleared.');
    }
}

module.exports = MinecraftAgent;
