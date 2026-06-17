class UtilityDecision {
    constructor(bot, hostiles) {
        this.bot = bot;
        this.hostiles = hostiles || ['zombie', 'skeleton', 'creeper', 'spider', 'husk', 'drowned', 'enderman'];
    }

    evaluate(target) {
        const health = this.bot.health || 20;
        
        let U_flee = 0;
        const nearbyHostile = Object.values(this.bot.entities).find(e => 
            e.type === 'mob' && this.hostiles.includes(e.name) && e.position.distanceTo(this.bot.entity.position) < 15
        );
        
        if (nearbyHostile) {
            // Only flee if there is actually a hostile mob nearby
            U_flee = 1 / (1 + Math.exp(-1.0 * (6 - health)));
        }

        // Oxygen urgency (only relevant when underwater)
        let U_surface = 0;
        if (this.bot.entity && this.bot.entity.isInWater) {
            const oxygen = this.bot.oxygenLevel !== undefined ? this.bot.oxygenLevel : 300;
            U_surface = 1 / (1 + Math.exp(-0.1 * (80 - oxygen)));
        }
        
        // Furi does NOT proactively fight mobs — he only fights back as a reflex
        // So U_fight stays at 0 here
        const U_fight = 0;

        const utilities = {
            'fight': U_fight,
            'flee': U_flee,
            'surface': U_surface
        };

        let bestAction = 'idle';
        let maxU = 0;

        for (const [action, u] of Object.entries(utilities)) {
            if (u > maxU) {
                maxU = u;
                bestAction = action;
            }
        }

        return bestAction;
    }
}

module.exports = UtilityDecision;
