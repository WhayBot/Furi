const mc = require('minecraft-protocol');

mc.ping({ host: 'LiveChat.aternos.me', port: 25565 }, (err, response) => {
    if (err) {
        console.error("Ping failed:", err);
    } else {
        console.log("Raw Server Ping Response:");
        console.dir(response, { depth: null });
    }
});
