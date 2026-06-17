/**
 * Block Interaction
 * Currently only contains mining capabilities (called manually, NOT automatically).
 * Furi will not mine on its own without a directive.
 */
class BlockInteraction {
    constructor(bot, inventoryManager, memory) {
        this.bot = bot;
        this.inventory = inventoryManager;
        this.memory = memory;
        this.isDigging = false;
    }

    /**
     * Mine a specific block.
     * Automatically equips the best tool before digging.
     */
    async digBlock(block) {
        if (this.isDigging) return false;
        if (!block || !this.bot.canDigBlock(block)) return false;

        this.isDigging = true;
        try {
            // Find and equip the best tool for this block
            const toolType = this.inventory.getToolTypeForBlock(block.name);
            if (toolType) {
                const tool = this.inventory.findBestTool(toolType);
                if (tool) {
                    await this.bot.equip(tool, 'hand');
                }
            }

            console.log(`[Interact] Mining ${block.name} at (${block.position.x}, ${block.position.y}, ${block.position.z})...`);
            await this.bot.dig(block);
            console.log(`[Interact] Successfully mined ${block.name}!`);
            this.memory.logEvent(`Mined ${block.name} at ${block.position.floored()}.`);

            // Re-equip weapon after mining
            const weapon = this.inventory.findBestWeapon();
            if (weapon) {
                await this.bot.equip(weapon, 'hand');
            }
            return true;
        } catch (e) {
            console.log(`[Interact] Mining failed: ${e.message}`);
            return false;
        } finally {
            this.isDigging = false;
        }
    }

    /**
     * Find nearest block by name.
     */
    findNearestBlock(blockName, maxDistance = 32) {
        return this.bot.findBlock({
            matching: block => block.name === blockName,
            maxDistance: maxDistance,
        });
    }

    /**
     * Check if currently mining.
     */
    get isBusy() {
        return this.isDigging;
    }
}

module.exports = BlockInteraction;
