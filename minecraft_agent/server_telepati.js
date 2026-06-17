const fs = require('fs');
const path = require('path');
const express = require('express');
const cors = require('cors');

const qTableFile = path.join(__dirname, 'q_table.json');
let qTable = {};
let _saving = false;

if (fs.existsSync(qTableFile)) {
    try {
        qTable = JSON.parse(fs.readFileSync(qTableFile, 'utf8'));
        const stateCount = Object.keys(qTable).filter(k => k !== '_metadata').length;
        console.log(`[Q-Learning] Loaded existing Q-Table with ${stateCount} states.`);
    } catch (err) {
        console.error("[Q-Learning] Failed to load Q-table.");
    }
}

const app = express();
app.use(cors());
app.use(express.json());

app.post('/teach', (req, res) => {
    const { state, action } = req.body;
    if (state && action) {
        if (!qTable[state]) {
            qTable[state] = { forward: 0, jump_forward: 0, left: 0, right: 0, back: 0, jump: 0 };
        }
        if (qTable[state][action] === undefined) {
            qTable[state][action] = 0;
        }
        
        qTable[state][action] = 100.0;
        
        // BUG-R2-13 Fix: Async write with debounce
        if (!_saving) {
            _saving = true;
            fs.writeFile(qTableFile, JSON.stringify(qTable), () => { _saving = false; });
        }
        
        console.log(`[Telepathy - RECORD ONLY] Learned human action: ${action} at state ${state}!`);
        res.status(200).send({ status: 'learned' });
    } else {
        res.status(400).send({ error: 'Missing state or action' });
    }
});

app.post('/teach-action', (req, res) => {
    const { type, target, tool } = req.body;
    if (type) {
        if (type === 'break_block') {
            console.log(`[Cognitive Telepathy] Learned to break: ${target} using ${tool}`);
        } else if (type === 'use_item') {
            console.log(`[Cognitive Telepathy] Learned to use item: ${target}`);
        }
        
        // This data could be saved to a specific json (e.g. cognitive_memory.json)
        // For now, we only display it as a visual log.
        
        res.status(200).send({ status: 'cognitive_learned' });
    } else {
        res.status(400).send({ error: 'Missing cognitive action type' });
    }
});

app.listen(3000, () => {
    console.log('======================================================');
    console.log('[Trainer] Telepathy Server (RECORD ONLY) running on http://localhost:3000');
    console.log('Furi is asleep and will not join the server.');
    console.log('You can train freely without consuming API Keys!');
    console.log('======================================================');
}).on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
        console.error('[Trainer] Port 3000 is already in use. Ensure previous Furi instances are closed.');
    } else {
        console.error('[Trainer] Error:', err.message);
    }
});
