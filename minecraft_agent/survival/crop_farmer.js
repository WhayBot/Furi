const vec3 = require('vec3');

/**
 * Crop Farmer
 * Allows Furi to harvest and replant crops when hungry and out of food.
 */
class CropFarmer {
    constructor(bot, steering, inventory, memory) {
        this.bot = bot;
        this.steering = steering;
        this.inventory = inventory;
        this.memory = memory;

        this.state = 'IDLE';
        this.targetCrop = null;
        this.lastFarmTime = 0;
        this.farmCooldown = 60000;

        this.crops = {
            'carrots': { mature: 7, seed: 'carrot' },
            'potatoes': { mature: 7, seed: 'potato' },
            'wheat': { mature: 7, seed: 'wheat_seeds' },
            'beetroots': { mature: 3, seed: 'beetroot_seeds' }
        };
    }

    /**
     * Attempts to find and harvest the nearest crop.
     * Returns true if actively farming.
     */
    async tryFarming() {
        if (Date.now() - this.lastFarmTime < this.farmCooldown && this.state === 'IDLE') {
            return false;
        }

        switch (this.state) {
            case 'IDLE':
                return this.startFarming();
            case 'WALKING':
                return this.handleWalking();
            case 'HARVESTING':
            case 'REPLANTING':
                // Sedang dalam proses async, biarkan state berjalan
                return true;
        }
        return false;
    }

    startFarming() {
        // Find nearest mature block
        const items = this.bot.inventory.items();
        let closestCrop = null;
        let closestDist = 16;

        this.bot.findBlocks({
            matching: (block) => {
                if (!block) return false;
                const cropInfo = this.crops[block.name];
                if (cropInfo) {
                    let age = 0;
                    if (block.getProperties && block.getProperties().age !== undefined) {
                        age = parseInt(block.getProperties().age);
                    } else {
                        age = block.metadata;
                    }
                    
                    if (age >= cropInfo.mature) {
                        const hasSeeds = items.some(i => i.name === cropInfo.seed);
                        const hasCrop = items.some(i => i.name === block.name);
                        
                        if (hasSeeds || hasCrop) {
                            const dist = this.bot.entity.position.distanceTo(block.position);
                            if (dist < closestDist) {
                                closestDist = dist;
                                closestCrop = block;
                            }
                        }
                    }
                }
                return false;
            },
            maxDistance: 16,
            count: 1
        });

        if (closestCrop) {
            console.log(`[Farming] Found mature ${closestCrop.name} at ${closestCrop.position}. Commencing farm cycle.`);
            this.targetCrop = closestCrop;
            this.state = 'WALKING';
            this.steering.setTarget(this.targetCrop.position, `Farming ${this.targetCrop.name}`);
            return true;
        }

        return false; // No ready farm found
    }

    async handleWalking() {
        if (!this.targetCrop) {
            this.reset();
            return false;
        }

        const furiPos = this.bot.entity.position;
        const cropPos = this.targetCrop.position;
        const dist = furiPos.distanceTo(cropPos);

        if (dist < 3) {
            this.steering.setTarget(null); // Stop walking
            await this.harvestAndReplant();
            return true;
        }

        // If Furi wandered too far
        if (dist > 20) {
            console.log(`[Farming] Furi is too far from farm target. Aborting farming.`);
            this.reset();
            return false;
        }

        return true; // Still walking
    }

    async harvestAndReplant() {
        this.state = 'HARVESTING';
        
        try {
            const cropName = this.targetCrop.name;
            const cropInfo = this.crops[cropName];
            if (!cropInfo) {
                console.log(`[Farming] Crop ${cropName} unrecognized. Aborting.`);
                this.reset();
                this.lastFarmTime = Date.now();
                return;
            }
            const seedName = cropInfo.seed;
            const cropPosition = this.targetCrop.position.clone();

            const blockToHarvest = this.bot.blockAt(cropPosition);
            if (!blockToHarvest || !this.bot.canDigBlock(blockToHarvest)) {
                console.log(`[Farming] Cannot dig block. Aborting.`);
                this.reset();
                this.lastFarmTime = Date.now();
                return;
            }
            
            console.log(`[Farming] Harvesting ${cropName}...`);
            await this.bot.dig(blockToHarvest);
            await this.bot.waitForTicks(20);

            this.state = 'REPLANTING';
            const farmlandPos = cropPosition.offset(0, -1, 0);
            const groundBlock = this.bot.blockAt(farmlandPos);

            if (groundBlock && groundBlock.name === 'farmland') {
                const items = this.bot.inventory.items();
                const seedItem = items.find(i => i.name === seedName);
                
                if (seedItem) {
                    console.log(`[Farming] Replanting ${seedName}...`);
                    await this.bot.equip(seedItem, 'hand');
                    
                    const lookPos = farmlandPos.offset(0.5, 1, 0.5);
                    const diff = lookPos.minus(this.bot.entity.position.offset(0, 1.62, 0));
                    const yaw = Math.atan2(-diff.x, -diff.z);
                    const pitch = Math.atan2(diff.y, Math.sqrt(diff.x * diff.x + diff.z * diff.z));
                    this.bot.cameraOscillator.setTargetYaw(yaw);
                    this.bot.cameraOscillator.setTargetPitch(pitch);
                    
                    await this.bot.placeBlock(groundBlock, vec3(0, 1, 0));
                    console.log(`[Farming] Successfully replanted.`);
                    this.memory.logEvent(`Farmed and replanted ${cropName}.`);
                } else {
                    console.log(`[Farming] No ${seedName} found to replant.`);
                    this.memory.logEvent(`Harvested ${cropName} but no seeds to replant.`);
                }
            } else {
                console.log(`[Farming] Block below is not farmland. Replant aborted.`);
            }

        } catch (e) {
            console.log(`[Farming] Farming failed: ${e.message}`);
        }

        this.reset();
        this.lastFarmTime = Date.now();
    }

    reset() {
        this.state = 'IDLE';
        this.targetCrop = null;
    }
}

module.exports = CropFarmer;
