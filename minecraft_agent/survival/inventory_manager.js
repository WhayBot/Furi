/**
 * Inventory Manager
 * Manages food selection, strongest weapons, and appropriate tools.
 */
class InventoryManager {
    constructor(bot) {
        this.bot = bot;

        // Food sorted by best saturation to worst
        this.FOOD_PRIORITY = [
            'enchanted_golden_apple', 'golden_apple', 'golden_carrot',
            'rabbit_stew', 'cooked_beef', 'cooked_porkchop',
            'cooked_mutton', 'cooked_salmon', 'beetroot_soup', 'mushroom_stew',
            'cooked_chicken', 'cooked_rabbit', 'bread', 'cooked_cod', 'baked_potato',
            'pumpkin_pie', 'apple', 'carrot', 'sweet_berries', 'melon_slice',
            'dried_kelp', 'raw_beef', 'raw_porkchop', 'raw_mutton',
            'raw_chicken', 'raw_cod', 'raw_salmon', 'cookie', 'potato',
        ];

        // Weapons sorted by best damage to worst
        this.WEAPON_PRIORITY = [
            'netherite_sword', 'diamond_sword', 'iron_sword',
            'netherite_axe', 'diamond_axe',
            'stone_sword', 'iron_axe',
            'golden_sword', 'stone_axe',
            'wooden_sword', 'golden_axe', 'wooden_axe',
        ];

        // Tool tier order
        this.TOOL_TIERS = ['netherite', 'diamond', 'iron', 'stone', 'golden', 'wooden'];
    }

    /**
     * Find best food in inventory (highest saturation first)
     */
    findBestFood() {
        const items = this.bot.inventory.items();
        for (const foodName of this.FOOD_PRIORITY) {
            const item = items.find(i => i.name === foodName);
            if (item) return item;
        }
        return null;
    }

    /**
     * Find strongest weapon in inventory
     */
    findBestWeapon() {
        const items = this.bot.inventory.items();
        for (const weaponName of this.WEAPON_PRIORITY) {
            const item = items.find(i => i.name === weaponName);
            if (item) return item;
        }
        return null;
    }

    /**
     * Find best tool by type (axe, pickaxe, shovel)
     */
    findBestTool(toolType) {
        const items = this.bot.inventory.items();
        for (const tier of this.TOOL_TIERS) {
            const item = items.find(i => i.name === `${tier}_${toolType}`);
            if (item) return item;
        }
        return null;
    }

    /**
     * Determine appropriate tool type for a specific block
     */
    getToolTypeForBlock(blockName) {
        if (blockName.includes('log') || blockName.includes('planks') || blockName.includes('wood')) {
            return 'axe';
        }
        if (['stone', 'cobblestone', 'andesite', 'diorite', 'granite', 'deepslate',
             'coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore', 'copper_ore',
             'bricks', 'nether', 'sandstone', 'terracotta'].some(n => blockName.includes(n))) {
            return 'pickaxe';
        }
        if (['dirt', 'sand', 'gravel', 'clay', 'soul_sand', 'snow', 'mud'].some(n => blockName.includes(n))) {
            return 'shovel';
        }
        return null;
    }

    /**
     * Check if a specific item exists in inventory
     */
    hasItem(itemName) {
        return this.bot.inventory.items().some(i => i.name === itemName);
    }

    /**
     * Count the total amount of a specific item
     */
    countItem(itemName) {
        return this.bot.inventory.items()
            .filter(i => i.name === itemName)
            .reduce((sum, i) => sum + i.count, 0);
    }

    /**
     * Detailed inventory summary for Groq Brain context
     */
    getInventorySummary() {
        const items = this.bot.inventory.items();
        if (items.length === 0) return 'Empty inventory';

        const grouped = {};
        for (const item of items) {
            grouped[item.name] = (grouped[item.name] || 0) + item.count;
        }

        return Object.entries(grouped)
            .map(([name, count]) => `${count}x ${name}`)
            .join(', ');
    }

    /**
     * Check if currently held item is a weapon
     */
    isHoldingWeapon() {
        const held = this.bot.heldItem;
        if (!held) return false;
        return this.WEAPON_PRIORITY.includes(held.name);
    }

    /**
     * Check if currently held item is the best available weapon
     */
    isHoldingBestWeapon() {
        const held = this.bot.heldItem;
        const best = this.findBestWeapon();
        if (!best) return true; // No weapon available, nothing to do
        if (!held) return false;
        return held.name === best.name;
    }
}

module.exports = InventoryManager;
