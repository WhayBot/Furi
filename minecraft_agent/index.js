require('dotenv').config();
const MinecraftAgent = require('./core');

const host = process.env.MC_HOST || 'localhost';
const port = parseInt(process.env.MC_PORT || '25565', 10);
const username = process.env.MC_USERNAME || 'NaturalAI';
// Use false for version to auto-detect if the server supports it, or specify string e.g. '26.1.2'
const version = process.env.MC_VERSION || false; 

const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

rl.question('Should Furi join the server? (y/n) [default: y]: ', (answer) => {
    const spawnBot = answer.toLowerCase() !== 'n';
    
    if (spawnBot) {
        let activeAgent = null;
        let retries = 0;
        const maxRetries = 5;

        function connectFuri() {
            console.log(`Starting Natural AI Bot connecting to ${host}:${port} as ${username} (Attempt ${retries + 1}/${maxRetries + 1})`);

            activeAgent = new MinecraftAgent({
                host: host,
                port: port,
                username: username,
                version: version
            });

            activeAgent.bot.on('error', err => console.error('Bot Error:', err.message));
            
            activeAgent.bot.on('end', (reason) => {
                console.log(`\n[System] Bot disconnected. Reason: ${reason}`);
                
                if (retries < maxRetries) {
                    retries++;
                    console.log(`[System] Attempting to reconnect in 5 seconds... (Attempt ${retries} of ${maxRetries})`);
                    setTimeout(() => {
                        if (activeAgent) {
                            activeAgent.destroy();
                        }
                        connectFuri();
                    }, 5000);
                } else {
                    console.log(`[System] Failed to reconnect after ${maxRetries} attempts. Terminating process.`);
                    process.exit(1);
                }
            });

            activeAgent.bot.on('spawn', () => {
                retries = 0; // Reset retry counter upon successful spawn
            });
        }

        connectFuri();

        rl.on('line', (input) => {
            const command = input.trim();
            if (command && activeAgent) {
                console.log(`[Directive Received] Setting new goal: "${command}"`);
                activeAgent.userDirective = command;
            }
        });
    } else {
        // Record Only Mode
        require('./server_telepati.js');
        // We do not close rl here if we want to keep the process alive, 
        // but express app.listen keeps it alive automatically.
    }
});
