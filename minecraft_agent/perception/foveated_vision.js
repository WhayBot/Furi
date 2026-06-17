class FoveatedVision {
    constructor(bot) {
        this.bot = bot;
        
        // Special weights for specific entity names
        this.nameWeights = {
            'squid': 20,
            'turtle': 20,
            'dolphin': 15
        };
        
        // Passive mobs that Furi can observe (weight: 10)
        this.passiveMobs = [
            'cow', 'pig', 'sheep', 'chicken', 'horse', 'donkey', 'mule',
            'llama', 'rabbit', 'fox', 'cat', 'wolf', 'parrot', 'bee',
            'axolotl', 'goat', 'frog', 'squid', 'turtle', 'dolphin',
            'cod', 'salmon', 'tropical_fish', 'pufferfish', 'mooshroom',
            'ocelot', 'panda', 'polar_bear', 'snow_golem', 'iron_golem',
            'villager', 'wandering_trader', 'strider', 'allay', 'camel', 'sniffer'
        ];
    }

    /**
     * Get weight for an entity based on its type and name.
     * Uses entity.type ('player', 'mob', etc.) instead of entity.name
     * because entity.name for players contains their USERNAME, not 'player'.
     */
    getEntityWeight(entity) {
        // 1. Specific name weights first (squid, turtle, dolphin)
        if (this.nameWeights[entity.name]) return this.nameWeights[entity.name];
        
        // 2. All players get high weight (entity.type === 'player')
        if (entity.type === 'player') return 100;
        
        // 3. Passive mob check by name
        if (this.passiveMobs.includes(entity.name)) return 10;
        
        // 4. Ignore everything else (hostile mobs, dropped items, arrows, etc.)
        return 0;
    }

    calculateSalience(entity) {
        const pos = this.bot.entity.position.offset(0, 1.62, 0); // eye position
        const targetPos = entity.position.offset(0, entity.height/2 || 1, 0);
        
        const distanceSq = pos.distanceSquared(targetPos);
        if (distanceSq < 0.1) return 0;

        const yawToTarget = Math.atan2(pos.x - targetPos.x, pos.z - targetPos.z);
        let diffYaw = this.bot.entity.yaw - yawToTarget;
        while (diffYaw > Math.PI) diffYaw -= 2 * Math.PI;
        while (diffYaw < -Math.PI) diffYaw += 2 * Math.PI;

        if (Math.abs(diffYaw) > Math.PI / 4) {
            return 0; // Outside FOV
        }

        const cosPhi = Math.abs(Math.cos(diffYaw));
        const baseWeight = this.getEntityWeight(entity);
        if (baseWeight === 0) return 0;

        const noise = 0.9 + Math.random() * 0.2;

        return (baseWeight * cosPhi / distanceSq) * noise;
    }

    getMostSalientTarget() {
        if (!this.bot.entities) return null;
        
        const entities = Object.values(this.bot.entities);
        let bestTarget = null;
        let maxSalience = -1;

        for (const entity of entities) {
            if (entity === this.bot.entity) continue;
            
            const salience = this.calculateSalience(entity);
            if (salience > maxSalience) {
                maxSalience = salience;
                bestTarget = entity;
            }
        }

        return bestTarget;
    }
}

module.exports = FoveatedVision;
