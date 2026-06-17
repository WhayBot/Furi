/**
 * Survival Instincts
 * Handles auto-eat, anti-drowning, and auto-equip best weapon.
 * This acts as a hardcoded reflex, completely separate from Q-Learning.
 */
class SurvivalInstincts {
    constructor(bot, inventoryManager, memory, cropFarmer) {
        this.bot = bot;
        this.inventory = inventoryManager;
        this.memory = memory;
        this.cropFarmer = cropFarmer;

        this.isEating = false;
        this.isSurfacing = false;
        this.lastEquippedWeapon = null;
    }

    /**
     * Auto-Eat: Consumes the best food when hunger drops below threshold.
     * Order: Best saturation prioritized.
     */
    async checkAndEat() {
        if (this.isEating) return false;
        if (this.bot.food >= 14) return false;

        const food = this.inventory.findBestFood();
        if (!food) {
            // Only log warning if strictly critical
            if (this.bot.food < 6) {
                console.log(`[Survival] Furi is starving (${this.bot.food}/20) but has no food!`);
                this.memory.logEvent(`Starving at ${this.bot.food}/20 hunger but no food available!`);
            }
            return false;
        }

        this.isEating = true;
        try {
            console.log(`[Survival] Eating ${food.name} (Hunger: ${this.bot.food}/20)`);
            await this.bot.equip(food, 'hand');
            await this.bot.consume();
            console.log(`[Survival] Finished eating! Hunger is now: ${this.bot.food}/20`);
            this.memory.logEvent(`Ate ${food.name}. Hunger is now ${this.bot.food}/20.`);

            // Re-equip weapon after eating (if any)
            const weapon = this.inventory.findBestWeapon();
            if (weapon) {
                await this.bot.equip(weapon, 'hand');
            }
            return true;
        } catch (e) {
            // Can fail if interrupted (e.g. attacked while eating)
            return false;
        } finally {
            this.isEating = false;
        }
    }

    /**
     * Anti-Drowning: Force surfacing when oxygen is low.
     * Returns true if in a drowning emergency.
     */
    checkDrowning() {
        if (!this.bot.entity.isInWater) {
            if (this.isSurfacing) {
                this.isSurfacing = false;
                this.bot.setControlState('jump', false);
            }
            return false;
        }

        // bot.oxygenLevel: 0-300 (300 = full, 0 = drowning)
        const oxygen = this.bot.oxygenLevel !== undefined ? this.bot.oxygenLevel : 300;

        if (oxygen < 60) { // Less than ~3 seconds of air left
            if (!this.isSurfacing) {
                console.log(`[Survival] Out of breath! Surfacing! (O2: ${oxygen}/300)`);
                this.memory.logEvent(`Almost drowned! Oxygen at ${oxygen}/300. Surfacing.`);
            }
            this.isSurfacing = true;
            this.bot.setControlState('jump', true);
            return true;
        }

        if (this.isSurfacing && oxygen > 150) {
            // Safe enough, stop panicking
            this.isSurfacing = false;
            this.bot.setControlState('jump', false);
            console.log(`[Survival] Oxygen level stabilized (O2: ${oxygen}/300)`);
        }

        return this.isSurfacing;
    }

    /**
     * Auto-Equip Weapon: Ensure Furi always holds its best weapon.
     * Only equips if the currently held item is NOT the best weapon.
     */
    async ensureBestWeaponEquipped() {
        if (this.isEating) return; // Do not interrupt eating

        const bestWeapon = this.inventory.findBestWeapon();
        if (!bestWeapon) return; // No weapon found

        // Already holding the best weapon?
        if (this.inventory.isHoldingBestWeapon()) return;

        try {
            await this.bot.equip(bestWeapon, 'hand');
            if (this.lastEquippedWeapon !== bestWeapon.name) {
                console.log(`[Survival] Furi drew ${bestWeapon.name}!`);
                this.memory.logEvent(`Equipped ${bestWeapon.name} as best weapon.`);
                this.lastEquippedWeapon = bestWeapon.name;
            }
        } catch (e) {
            // Can fail if performing another action
        }
    }

    /**
     * Main update — called every ~1 second from survival loop.
     * Returns string describing current action, or null if idle.
     */
    async update() {
        // Priority 1: Do not drown!
        if (this.checkDrowning()) {
            return 'surfacing';
        }

        // Priority 2: Eat if hungry
        if (this.bot.food < 14) {
            const ate = await this.checkAndEat();
            if (ate) return 'eating';
        }

        // Priority 2.5: Try to farm if starving and out of food
        if (this.bot.food < 14) {
            // If inventory has no food OR food < 6
            if (!this.inventory.findBestFood() || this.bot.food <= 6) {
                if (this.cropFarmer) {
                    const farming = await this.cropFarmer.tryFarming();
                    if (farming) return 'farming';
                }
            }
        }

        // Priority 3: Ensure best weapon is equipped
        await this.ensureBestWeaponEquipped();

        return null;
    }
}

module.exports = SurvivalInstincts;
