# Furi - Natural AI Minecraft Agent

Furi is an advanced Minecraft AI agent built using Node.js and Mineflayer. It utilizes a combination of traditional game-playing AI (reflexes, pathfinding), Q-Learning for low-level navigation, and a Large Language Model (Groq Llama 3) for high-level cognitive decision making.

## Core Features

- **Groq LLM Brain**: Furi uses a Groq-powered LLM to process high-level user directives (e.g., "Survive and thrive", "Build a house", "Farm crops") and translate them into actionable macro-strategies (Explore, Flee). It also analyzes its deaths to generate "Life Lessons" (e.g., "Never fight a creeper without armor").
- **Q-Learning Navigation**: Furi learns to navigate the Minecraft world through reinforcement learning. It receives positive rewards for reaching targets and negative rewards for getting stuck or falling. Over time, it learns to bypass complex obstacles.
- **Foveated Vision**: Furi uses a realistic vision system that calculates the "salience" of nearby entities. It prioritizes looking at players, passive mobs, and specific interesting entities (like dolphins or turtles) while ignoring irrelevant items, mimicking human attention.
- **Survival Instincts (Reflexes)**: Hardcoded survival mechanisms ensure Furi stays alive. This includes auto-eating the best available food when hungry, surfacing when drowning, and equipping the best weapon when threatened.
- **Crop Farming**: When hungry and out of food, Furi can automatically detect mature crops, harvest them, and replant the seeds to ensure a sustainable food source.
- **Telepathy Trainer Mod**: A companion Fabric mod (Furi Trainer) that allows a human player to "train" Furi. The mod records the human's actions (movement, jumping, block breaking, item usage) and sends them to Furi's Q-Table, allowing the AI to learn from human demonstrations.

## Architecture

The project is divided into several modules:

- `core.js`: The central orchestrator. It manages the main update loops (Macro Strategy, Cognitive Loop, Physics Loop) and integrates all other modules.
- `index.js`: The entry point. Handles connecting Furi to the server or launching the Telepathy Trainer server in "record only" mode.
- `groq_brain.js`: Interfaces with the Groq API for high-level decision making and reflection.
- `server_telepati.js`: An Express server that receives training data from the Furi Trainer Fabric mod.
- `trainer.js`: A specialized CCTV bot that observes a human player and saves their actions into the Q-Table.
- `brain/`: Contains `memory.js` (short-term and long-term memory) and `utility_decision.js` (evaluates fight/flee/surface utilities).
- `combat/`: Contains `gaussian_aim.js`, which applies realistic Fitts's Law-based aiming errors during combat.
- `interaction/`: Contains `block_interaction.js` for mining capabilities.
- `perception/`: Contains `foveated_vision.js` for visual attention calculation.
- `physics/`: Contains `camera_oscillator.js` (smooth, damped harmonic oscillator for camera movement) and `q_learning_navigation.js` (the reinforcement learning navigation system).
- `survival/`: Contains `survival_instincts.js`, `inventory_manager.js`, and `crop_farmer.js`.

## Setup and Installation

### Prerequisites

- Node.js (v18 or higher recommended)
- Minecraft Java Edition
- Fabric Loader (for the Trainer Mod)

### Installation

1. Clone the repository.
2. Run `npm install` in the `minecraft_agent` directory to install dependencies (mineflayer, groq-sdk, express, cors, dotenv).
3. Copy or rename the `.env.example` file to `.env` in the `minecraft_agent` directory and configure it with your settings:

```env
MC_HOST=localhost
MC_PORT=25565
MC_USERNAME=your_agent_name
MC_VERSION=1.21.4

GROQ_MODEL=your_groq_model_name

GROQ_API_KEY=your_groq_api_key_1
GROQ_API_KEY_2=your_groq_api_key_2
GROQ_API_KEY_3=your_groq_api_key_3
```

### Running Furi

To start Furi and connect it to the server:

```bash
node index.js
```

You will be prompted to choose whether Furi should join the server.

- If you answer `y` (default), Furi will connect to the server and begin operating based on its AI.
- If you answer `n`, the script will start the Telepathy Server in "Record Only" mode, allowing you to train the Q-Table using the Fabric mod without spawning the bot.

## Training with the Furi Trainer Mod

1. Install the Fabric mod located in the `furi-trainer-mod` directory into your Minecraft client.
2. Start the Telepathy Server (either by running `node index.js` and selecting `n`, or running `node server_telepati.js`).
3. In Minecraft, press the `O` key to toggle the recording state. When recording is ON, your movements and actions are sent to the local server to train Furi's Q-Table.

## Notes

- **Q-Learning Navigation**: Furi relies heavily on its `q_table.json` file for navigation. If the file is missing, Furi will start exploring completely randomly until it learns.
- **Resetting / Retraining Furi**: The provided `q_table.json` already contains pre-trained navigation data. If you want to reset Furi's memory and retrain it from scratch, simply delete or rename the `q_table.json` file. The system will automatically create a new, empty one the next time Furi runs or when you train it using the Telepathy Server.
- Ensure the `GROQ_API_KEY` is valid, as Furi uses it for dynamic goal setting and reflection after death. Multiple keys can be passed as an array in the code to bypass rate limits.
