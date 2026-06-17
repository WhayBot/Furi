const Groq = require('groq-sdk');

class GroqBrain {
    constructor(apiKeys) {
        if (!Array.isArray(apiKeys)) apiKeys = [apiKeys];
        this.apiKeys = apiKeys;
        this.currentKeyIndex = 0;
        this.groq = new Groq({ apiKey: this.apiKeys[this.currentKeyIndex] });
        this.model = process.env.GROQ_MODEL || 'llama-3.1-8b-instant';
    }

    switchKey() {
        if (this.apiKeys.length > 1) {
            this.currentKeyIndex = (this.currentKeyIndex + 1) % this.apiKeys.length;
            this.groq = new Groq({ apiKey: this.apiKeys[this.currentKeyIndex] });
            console.log(`\n[GroqBrain] ⚠️ Rate Limit hit! Switching to API Key #${this.currentKeyIndex + 1} / ${this.apiKeys.length}...`);
            return true;
        }
        return false;
    }

    async createChatCompletion(options) {
        let retries = this.apiKeys.length;
        while (retries > 0) {
            try {
                return await this.groq.chat.completions.create(options);
            } catch (e) {
                if (e.status === 429 || (e.message && e.message.includes('429'))) {
                    if (this.switchKey()) {
                        retries--;
                        continue; // Try again with the next key
                    }
                }
                throw e; // Rethrow if not 429 or no more keys to try
            }
        }
        throw new Error("All API keys rate limited.");
    }

    async decideMacroStrategy(state) {
        const prompt = `You are Furi, an AI playing Minecraft. You are exploring and surviving.

**User Directive (Highest Priority):**
"${state.userDirective || "Survive and thrive"}"

**Life Lessons (Rules from past mistakes):**
${state.lifeLessons || "None yet."}

**Recent Memory:**
${state.recentEvents || "No recent events."}

**Current State:**
- Health: ${state.health}/20
- Hunger: ${state.hunger}/20
- Inventory: ${state.inventory}
- Nearby Blocks: ${state.nearby}

Based on the above, decide your next strategy.
Rules:
- If hunger < 10 and you have food, prioritize eating (your survival system handles this automatically).
- If health < 8, prioritize fleeing from danger.
- Otherwise, explore the world and observe your surroundings.
- You can mine blocks if directed, and you can automatically farm crops when hungry.

Respond in strict JSON format:
{"strategy": "brief description of why", "action": "EXPLORE|FLEE"}`;

        try {
            const chatCompletion = await this.createChatCompletion({
                messages: [{ role: 'user', content: prompt }],
                model: this.model,
                temperature: 0.5,
                response_format: { type: 'json_object' }
            });
            
            return JSON.parse(chatCompletion.choices[0].message.content);
        } catch (e) {
            console.error("Groq API Error:", e.message);
            return { action: "EXPLORE", strategy: "fallback" };
        }
    }

    async reflectOnDeath(recentEvents) {
        const prompt = `You are playing Minecraft and you just died.
Here is the log of what happened right before you died:
${recentEvents}

Analyze the events. Why did you die? What mistake did you make?
Formulate a short, strict "Life Lesson" rule to avoid this in the future (max 1 sentence).
Example: "Never fight creepers without armor." or "Run away immediately when health falls below 10."

Respond in strict JSON format:
{"lesson": "the rule you learned"}`;

        try {
            const chatCompletion = await this.createChatCompletion({
                messages: [{ role: 'user', content: prompt }],
                model: this.model,
                temperature: 0.7,
                response_format: { type: 'json_object' }
            });
            
            const response = JSON.parse(chatCompletion.choices[0].message.content);
            return response.lesson;
        } catch (e) {
            console.error("Groq Reflection Error:", e.message);
            return null;
        }
    }
}

module.exports = GroqBrain;
