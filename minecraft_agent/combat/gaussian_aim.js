class GaussianAim {
    constructor() {
        this.baseStdDev = 0.05; // Base error
    }

    // Generate random number with normal distribution (Box-Muller transform)
    randomGaussian() {
        let u = 0, v = 0;
        while(u === 0) u = Math.random(); // Converting [0,1) to (0,1)
        while(v === 0) v = Math.random();
        return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    }

    // Fitts's Law + Panic factor to calculate error standard deviation
    calculateErrorStdDev(mouseVelocity, panicLevel) {
        // k * v_mouse * S_panic
        const k = 0.02;
        return Math.max(this.baseStdDev, k * mouseVelocity * panicLevel);
    }

    // Apply error to target position
    applyAimError(targetPos, mouseVelocity, panicLevel) {
        const stdDev = this.calculateErrorStdDev(mouseVelocity, panicLevel);
        
        // Add gaussian noise to x, y, z
        const errorX = this.randomGaussian() * stdDev;
        const errorY = this.randomGaussian() * stdDev;
        const errorZ = this.randomGaussian() * stdDev;

        return targetPos.offset(errorX, errorY, errorZ);
    }
}

module.exports = GaussianAim;
