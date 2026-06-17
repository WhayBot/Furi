class SteeringNavigation {
    constructor(bot) {
        this.bot = bot;
        this.target = null;
        this.stuckTimer = 0;
        this.lastPos = null;
    }

    setTarget(pos) {
        this.target = pos;
        if (!pos) {
            this.bot.setControlState('forward', false);
            this.bot.setControlState('jump', false);
        }
    }

    update() {
        if (!this.target) return;

        const pos = this.bot.entity.position;
        const dist = pos.distanceTo(this.target);

        if (dist < 1.5) {
            this.bot.setControlState('forward', false);
            this.bot.setControlState('jump', false);
            this.target = null;
            return;
        }

        // Look at target
        const diff = this.target.minus(pos);
        const yaw = Math.atan2(-diff.x, -diff.z);
        this.bot.look(yaw, 0, true);
        this.bot.setControlState('forward', true);

        // Proactive Jump Logic (Detect obstacles 1-2 blocks ahead)
        const dirX = -Math.sin(yaw);
        const dirZ = -Math.cos(yaw);
        
        const block1 = this.bot.blockAt(pos.offset(dirX * 1, 0, dirZ * 1));
        const block2 = this.bot.blockAt(pos.offset(dirX * 1.5, 0, dirZ * 1.5));
        const block1Head = this.bot.blockAt(pos.offset(dirX * 1, 1, dirZ * 1));
        
        const isSolid = (b) => b && b.name !== 'air' && b.name !== 'water' && b.name !== 'grass' && b.name !== 'tall_grass';

        let needsToJump = false;
        // If there's a solid block ahead at feet level, and space at head level
        if ((isSolid(block1) || isSolid(block2)) && (!block1Head || !isSolid(block1Head))) {
            needsToJump = true;
        }

        if (needsToJump) {
            this.bot.setControlState('jump', true);
            this.bot.setControlState('sprint', true); // Sprint while jumping helps clear gaps
        } else {
            this.bot.setControlState('sprint', false);
        }

        // Fallback: Simple Anti-Stuck Jump Logic
        if (this.lastPos) {
            const movedDist = pos.distanceTo(this.lastPos);
            if (movedDist < 0.2) {
                this.stuckTimer++;
                
                // Check if jumping is even possible (is there a block at head level?)
                const jumpIsFutile = isSolid(block1Head);
                
                if (this.stuckTimer > 5) {
                    if (!jumpIsFutile) {
                        this.bot.setControlState('jump', true);
                    } else {
                        // 2-block high wall! Don't jump, start strafing immediately to slide around it
                        this.bot.setControlState('jump', false);
                        this.bot.setControlState('left', true); // Strafe left
                    }
                }
                if (this.stuckTimer > 15) {
                    this.bot.setControlState('jump', false);
                    this.bot.setControlState('left', Math.random() > 0.5);
                    this.bot.setControlState('right', Math.random() > 0.5);
                }
            } else {
                this.stuckTimer = 0;
                if (!needsToJump) {
                    this.bot.setControlState('jump', false);
                }
                this.bot.setControlState('left', false);
                this.bot.setControlState('right', false);
            }
        }
        
        this.lastPos = pos.clone();
    }
}

module.exports = SteeringNavigation;
