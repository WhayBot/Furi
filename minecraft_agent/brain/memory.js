const fs = require('fs');
const path = require('path');

class Memory {
    constructor(memoryFile = 'memory.json') {
        this.memoryPath = path.join(__dirname, '..', memoryFile);
        this.recentEvents = []; // Short-term memory (last 10 events)
        this.lifeLessons = [];  // Long-term memory (rules learned)
        this.load();
    }

    load() {
        if (fs.existsSync(this.memoryPath)) {
            try {
                const data = JSON.parse(fs.readFileSync(this.memoryPath, 'utf8'));
                this.lifeLessons = data.lifeLessons || [];
            } catch (e) {
                console.error("Failed to load memory:", e.message);
            }
        }
    }
    save() {
        try {
            fs.writeFile(this.memoryPath, JSON.stringify({ lifeLessons: this.lifeLessons }, null, 2), (err) => {
                if (err) console.error("Failed to save memory:", err.message);
            });
        } catch (e) {
            console.error("Failed to save memory:", e.message);
        }
    }

    logEvent(eventDescription) {
        const timestamp = new Date().toTimeString().split(' ')[0];
        this.recentEvents.push(`[${timestamp}] ${eventDescription}`);
        
        // Keep only the last 10 events
        if (this.recentEvents.length > 10) {
            this.recentEvents.shift();
        }
    }

    getRecentEvents() {
        return this.recentEvents.join('\n');
    }

    addLifeLesson(lesson) {
        if (!this.lifeLessons.includes(lesson)) {
            this.lifeLessons.push(lesson);
            this.save();
        }
    }

    getLifeLessons() {
        if (this.lifeLessons.length === 0) return "None yet.";
        return this.lifeLessons.map((l, i) => `${i + 1}. ${l}`).join('\n');
    }
}

module.exports = Memory;
