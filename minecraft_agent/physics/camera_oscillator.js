class CameraOscillator {
    constructor(bot) {
        this.bot = bot;
        this.currentYaw = 0;
        this.targetYaw = 0;
        this.velocityYaw = 0;
        
        this.currentPitch = 0;
        this.targetPitch = 0;
        this.velocityPitch = 0;

        // Tuning parameters
        this.omega0 = 15.0; // Angular frequency (aggressiveness)
        this.zeta = 1.0;    // Damping ratio (1.0 = critical, <1 = underdamped/bounce)
        this.initialized = false;
    }

    setTargetYaw(yaw) {
        this.targetYaw = yaw;
    }

    setTargetPitch(pitch) {
        this.targetPitch = pitch;
    }

    setPanicMode(isPanic) {
        if (isPanic) {
            this.zeta = 0.6; // Bouncy, overcompensates
            this.omega0 = 25.0; // Fast
        } else {
            this.zeta = 1.0; // Smooth, precise
            this.omega0 = 15.0;
        }
    }

    update(dt = 0.05) {
        // Init current angles from bot if this is first frame
        if (!this.initialized && this.bot.entity) {
            this.currentYaw = this.bot.entity.yaw;
            this.currentPitch = this.bot.entity.pitch;
            if (this.targetYaw === 0) this.targetYaw = this.bot.entity.yaw;
            if (this.targetPitch === 0) this.targetPitch = this.bot.entity.pitch;
            this.initialized = true;
        }

        // Sub-step integration for mathematical stability
        const subSteps = 10;
        const subDt = dt / subSteps;

        for (let i = 0; i < subSteps; i++) {
            // Normalize angle difference to [-PI, PI]
            let diffYaw = this.currentYaw - this.targetYaw;
            while (diffYaw > Math.PI) diffYaw -= 2 * Math.PI;
            while (diffYaw < -Math.PI) diffYaw += 2 * Math.PI;

            // Damped Harmonic Oscillator for Yaw
            const alphaYaw = -2 * this.zeta * this.omega0 * this.velocityYaw - (this.omega0 * this.omega0) * diffYaw;
            this.velocityYaw += alphaYaw * subDt;
            this.currentYaw += this.velocityYaw * subDt;

            // Damped Harmonic Oscillator for Pitch
            const diffPitch = this.currentPitch - this.targetPitch;
            const alphaPitch = -2 * this.zeta * this.omega0 * this.velocityPitch - (this.omega0 * this.omega0) * diffPitch;
            this.velocityPitch += alphaPitch * subDt;
            this.currentPitch += this.velocityPitch * subDt;
            
            // BUG-R2-11 Fix: Clamp pitch between -PI/2 and PI/2 to prevent camera flipping
            this.currentPitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.currentPitch));
        }

        // Apply to bot, true = force skip Mineflayer's internal smooth look
        this.bot.look(this.currentYaw, this.currentPitch, true);
    }
}

module.exports = CameraOscillator;
