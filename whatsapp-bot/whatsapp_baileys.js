const express = require('express');
const fs = require('fs');
const path = require('path');

// CONFIGURAÇÃO CLOUD RUN
const CONFIG = {
    phoneNumber: process.env.WHATSAPP_PHONE_NUMBER || '+5511918368812',
    whatsappWebVersion: [2, 3000, 1026946712],
    sessionPath: './whatsapp_session',
    expressPort: parseInt(process.env.PORT) || 8080,
    isCloudRun: process.env.K_SERVICE !== undefined,
    maxRetries: 3,
    retryDelay: 15000,
    maxMemoryUsage: 200 * 1024 * 1024 // 200MB
};

// ESTADO GLOBAL
let appState = {
    serverReady: false,
    whatsappConnected: false,
    whatsappInitializing: false,
    firebaseConnected: false,
    initializationComplete: false,
    lastError: null,
    startTime: new Date()
};

// Firebase globals
let firebaseDb = null;
let firebaseStorage = null;
let storageBucket = null;
let qrCodeBase64 = null;

// Express app - INICIALIZAÇÃO IMEDIATA
const app = express();
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));
app.set('trust proxy', true);
app.disable('x-powered-by');

// HEALTH CHECK CRÍTICO - Deve responder IMEDIATAMENTE
app.get('/health', (req, res) => {
    const uptime = Math.floor((new Date() - appState.startTime) / 1000);
    const status = appState.serverReady ? 'healthy' : 'starting';
    
    res.status(200).json({
        status: status,
        server_ready: appState.serverReady,
        whatsapp_connected: appState.whatsappConnected,
        whatsapp_initializing: appState.whatsappInitializing,
        firebase_connected: appState.firebaseConnected,
        initialization_complete: appState.initializationComplete,
        uptime_seconds: uptime,
        last_error: appState.lastError,
        timestamp: new Date().toISOString(),
        cloud_run: CONFIG.isCloudRun,
        port: CONFIG.expressPort
    });
});

// ROOT ENDPOINT
app.get('/', (req, res) => {
    res.json({
        service: 'WhatsApp Baileys Bot - Cloud Run',
        status: appState.serverReady ? 'running' : 'starting',
        whatsapp_status: appState.whatsappConnected ? 'connected' : 
                         appState.whatsappInitializing ? 'connecting' : 'disconnected',
        firebase_status: appState.firebaseConnected ? 'connected' : 'disconnected',
        uptime: Math.floor((new Date() - appState.startTime) / 1000) + 's',
        endpoints: ['/health', '/qr', '/api/qr-status', '/send-message']
    });
});

// QR CODE ENDPOINT
app.get('/qr', (req, res) => {
    const status = appState.whatsappConnected ? 'Conectado ✅' : 
                   appState.whatsappInitializing ? 'Conectando...' : 'Desconectado';
    
    const qrDisplay = qrCodeBase64 && !appState.whatsappConnected 
        ? `<img src="${qrCodeBase64}" style="max-width:300px;border:2px solid #25D366;border-radius:10px;">
           <p>Escaneie o QR Code com seu WhatsApp</p>` 
        : appState.whatsappConnected 
        ? '<p style="color: green;">✅ WhatsApp Conectado com Sucesso!</p>'
        : '<p>Aguardando conexão...</p>';
    
    res.send(`
<!DOCTYPE html>
<html>
<head>
    <title>WhatsApp Bot - Cloud Run</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 20px; background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); min-height: 100vh; margin: 0; }
        .container { max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .status { font-size: 18px; margin: 20px 0; font-weight: bold; }
        .connected { color: #25D366; }
        .connecting { color: #ff9800; }
        .disconnected { color: #f44336; }
        .info { background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 15px 0; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 WhatsApp Bot</h1>
        <div class="status ${appState.whatsappConnected ? 'connected' : appState.whatsappInitializing ? 'connecting' : 'disconnected'}">${status}</div>
        ${qrDisplay}
        <div class="info">
            <strong>Cloud Run Status:</strong><br>
            Server: ${appState.serverReady ? '✅' : '⏳'} | 
            Firebase: ${appState.firebaseConnected ? '✅' : '❌'} | 
            Uptime: ${Math.floor((new Date() - appState.startTime) / 1000)}s
        </div>
        <p><small>Auto-refresh a cada 10 segundos</small></p>
    </div>
</body>
</html>`);
});

// QR STATUS API
app.get('/api/qr-status', (req, res) => {
    res.json({
        hasQR: !!qrCodeBase64,
        whatsappConnected: appState.whatsappConnected,
        whatsappInitializing: appState.whatsappInitializing,
        firebaseConnected: appState.firebaseConnected,
        serverReady: appState.serverReady,
        timestamp: new Date().toISOString()
    });
});

// SEND MESSAGE ENDPOINT
app.post('/send-message', async (req, res) => {
    try {
        const { to, message } = req.body;
        
        if (!to || !message) {
            return res.status(400).json({ 
                success: false, 
                error: 'Missing required fields: to, message' 
            });
        }
        
        if (!appState.whatsappConnected) {
            return res.status(503).json({ 
                success: false, 
                error: 'WhatsApp not connected',
                status: appState.whatsappInitializing ? 'connecting' : 'disconnected'
            });
        }
        
        const messageId = await sendWhatsAppMessage(to, message);
        await saveMessageToFirebase(to, message, 'sent');
        
        res.json({ 
            success: true, 
            messageId, 
            to, 
            timestamp: new Date().toISOString() 
        });
        
    } catch (error) {
        console.error('Send message error:', error.message);
        res.status(500).json({ 
            success: false, 
            error: error.message 
        });
    }
});

// VARIÁVEIS GLOBAIS DO BOT
let sock = null;
let authState = null;
let saveCreds = null;

// INICIALIZAR SERVIDOR HTTP IMEDIATAMENTE
console.log('🚀 Starting WhatsApp Bot for Cloud Run...');
console.log('☁️ Cloud Run Environment:', CONFIG.isCloudRun);
console.log('🔌 Port:', CONFIG.expressPort);

const server = app.listen(CONFIG.expressPort, '0.0.0.0', () => {
    console.log(`✅ HTTP Server READY on port ${CONFIG.expressPort}`);
    appState.serverReady = true;
    
    // CRÍTICO: Inicializar serviços APÓS servidor estar online
    setTimeout(() => {
        console.log('📱 Starting background initialization...');
        initializeServices();
    }, 1000);
});

server.on('error', (error) => {
    console.error('❌ Server error:', error.message);
    appState.lastError = error.message;
    if (error.code === 'EADDRINUSE') {
        process.exit(1);
    }
});

// FIREBASE INITIALIZATION
async function initializeFirebase() {
    try {
        if (!process.env.FIREBASE_KEY) {
            console.log('⚠️ FIREBASE_KEY not found - running without Firebase');
            return false;
        }

        console.log('🔥 Initializing Firebase...');
        const admin = require('firebase-admin');
        
        const firebaseKey = JSON.parse(process.env.FIREBASE_KEY);
        const credential = admin.credential.cert(firebaseKey);
        
        if (!admin.apps.length) {
            admin.initializeApp({ 
                credential,
                storageBucket: process.env.FIREBASE_STORAGE_BUCKET
            });
        }
        
        firebaseDb = admin.firestore();
        firebaseStorage = admin.storage();
        storageBucket = firebaseStorage.bucket();
        
        // Test connection
        await firebaseDb.collection('_health_check').doc('whatsapp_bot').set({
            timestamp: new Date(),
            service: 'whatsapp_baileys_bot',
            status: 'cloud_run_initialized'
        });
        
        appState.firebaseConnected = true;
        console.log('✅ Firebase connected');
        return true;
        
    } catch (error) {
        console.error('❌ Firebase error:', error.message);
        appState.lastError = `Firebase: ${error.message}`;
        return false;
    }
}

// SAVE MESSAGE TO FIREBASE
async function saveMessageToFirebase(from, message, direction = 'received') {
    try {
        if (!firebaseDb || !appState.firebaseConnected) {
            return;
        }
        
        const cleanPhone = from ? from.replace('@s.whatsapp.net', '') : 'unknown';
        
        await firebaseDb.collection('whatsapp_messages').add({
            from: from || 'unknown',
            message: message || '',
            direction: direction,
            timestamp: new Date(),
            bot_service: 'baileys_cloud',
            phone_clean: cleanPhone
        });
        
        console.log(`💾 Message ${direction} saved to Firebase`);
    } catch (error) {
        console.error('❌ Firebase save error:', error.message);
    }
}

// SESSION MANAGER SIMPLIFICADO
class CloudSessionManager {
    constructor() {
        this.sessionPath = './whatsapp_session';
        this.cloudPath = 'whatsapp-sessions/baileys-session';
    }

    async downloadSession() {
        try {
            if (!storageBucket) {
                console.log('⚠️ Storage not available - using local session');
                return false;
            }

            console.log('📥 Downloading session from Cloud Storage...');
            
            if (!fs.existsSync(this.sessionPath)) {
                fs.mkdirSync(this.sessionPath, { recursive: true });
            }

            const [files] = await storageBucket.getFiles({
                prefix: this.cloudPath
            });

            if (files.length === 0) {
                console.log('📂 No session found in cloud');
                return false;
            }

            let downloaded = 0;
            for (const file of files.slice(0, 10)) { // Limit for Cloud Run
                try {
                    const fileName = file.name.replace(`${this.cloudPath}/`, '');
                    if (!fileName || fileName === this.cloudPath) continue;
                    
                    const localPath = path.join(this.sessionPath, fileName);
                    await file.download({ destination: localPath });
                    downloaded++;
                } catch (downloadError) {
                    console.error(`Download error ${file.name}:`, downloadError.message);
                }
            }

            console.log(`✅ Session restored: ${downloaded} files`);
            return downloaded > 0;

        } catch (error) {
            console.error('❌ Download session error:', error.message);
            return false;
        }
    }

    async uploadSession() {
        try {
            if (!storageBucket || !fs.existsSync(this.sessionPath)) {
                return false;
            }

            const files = fs.readdirSync(this.sessionPath);
            let uploaded = 0;

            for (const fileName of files.slice(0, 15)) { // Limit for Cloud Run
                try {
                    const localPath = path.join(this.sessionPath, fileName);
                    const cloudPath = `${this.cloudPath}/${fileName}`;
                    
                    const stats = fs.statSync(localPath);
                    if (stats.isFile() && stats.size < 5 * 1024 * 1024) { // Max 5MB
                        await storageBucket.upload(localPath, {
                            destination: cloudPath,
                            metadata: { contentType: 'application/octet-stream' }
                        });
                        uploaded++;
                    }
                } catch (uploadError) {
                    console.error(`Upload error ${fileName}:`, uploadError.message);
                }
            }

            if (uploaded > 0) {
                console.log(`✅ Session backed up: ${uploaded} files`);
            }
            return true;

        } catch (error) {
            console.error('❌ Upload session error:', error.message);
            return false;
        }
    }
}

// INITIALIZE SERVICES
async function initializeServices() {
    try {
        console.log('🚀 Initializing background services...');
        
        // Initialize Firebase
        await initializeFirebase();
        
        // Initialize session manager
        const sessionManager = new CloudSessionManager();
        if (appState.firebaseConnected) {
            await sessionManager.downloadSession();
        }
        
        // Wait a bit then initialize WhatsApp
        setTimeout(async () => {
            await initializeWhatsApp();
        }, 2000);
        
    } catch (error) {
        console.error('❌ Service initialization error:', error.message);
        appState.lastError = `Services: ${error.message}`;
    }
}

// INITIALIZE WHATSAPP
async function initializeWhatsApp() {
    if (appState.whatsappInitializing) {
        console.log('⚠️ WhatsApp already initializing');
        return;
    }

    appState.whatsappInitializing = true;
    console.log('📱 Initializing WhatsApp Baileys...');

    try {
        // Import Baileys
        const baileys = require('@whiskeysockets/baileys');
        const { Boom } = require('@hapi/boom');
        const qrcode = require('qrcode-terminal');
        const QRCode = require('qrcode');
        
        const makeWASocket = baileys.makeWASocket || baileys.default?.makeWASocket;
        const DisconnectReason = baileys.DisconnectReason || baileys.default?.DisconnectReason;
        const useMultiFileAuthState = baileys.useMultiFileAuthState || baileys.default?.useMultiFileAuthState;
        
        if (typeof makeWASocket !== 'function') {
            throw new Error('makeWASocket not found');
        }
        
        // Create session directory
        if (!fs.existsSync(CONFIG.sessionPath)) {
            fs.mkdirSync(CONFIG.sessionPath, { recursive: true });
        }

        // Setup auth state
        const { state, saveCreds: saveCredentials } = await useMultiFileAuthState(CONFIG.sessionPath);
        authState = state;
        saveCreds = saveCredentials;

        // Connect to WhatsApp
        await connectToWhatsApp(makeWASocket, DisconnectReason, Boom, qrcode, QRCode);
        
    } catch (error) {
        console.error('❌ WhatsApp initialization error:', error.message);
        appState.lastError = `WhatsApp: ${error.message}`;
        appState.whatsappInitializing = false;
        
        // Retry after delay
        setTimeout(() => {
            console.log('🔄 Retrying WhatsApp initialization...');
            initializeWhatsApp();
        }, CONFIG.retryDelay);
    }
}

// CONNECT TO WHATSAPP
async function connectToWhatsApp(makeWASocket, DisconnectReason, Boom, qrcode, QRCode) {
    try {
        console.log('🔌 Connecting to WhatsApp Web...');
        
        sock = makeWASocket({
            auth: authState,
            version: CONFIG.whatsappWebVersion,
            printQRInTerminal: false,
            browser: ['WhatsApp Bot', 'Chrome', '110.0.0'],
            defaultQueryTimeoutMs: 30000,
            connectTimeoutMs: 30000,
            keepAliveIntervalMs: 25000,
            markOnlineOnConnect: false,
            generateHighQualityLinkPreview: false,
            syncFullHistory: false,
            shouldSyncHistoryMessage: () => false,
            retryRequestDelayMs: 200,
            maxMsgRetryCount: 2,
            qrTimeout: 60000,
            connectCooldownMs: 3000
        });
        
        setupEventHandlers(DisconnectReason, Boom, qrcode, QRCode);
        
    } catch (error) {
        console.error('❌ Connect error:', error.message);
        throw error;
    }
}

// SETUP EVENT HANDLERS
function setupEventHandlers(DisconnectReason, Boom, qrcode, QRCode) {
    let qrAttempts = 0;
    const maxQRAttempts = 3;
    
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            qrAttempts++;
            console.log(`📱 QR Code generated (${qrAttempts}/${maxQRAttempts})`);
            
            try {
                // Terminal QR
                qrcode.generate(qr, { small: true });
                
                // Web QR
                qrCodeBase64 = await QRCode.toDataURL(qr, {
                    width: 256,
                    margin: 2,
                    errorCorrectionLevel: 'M'
                });
                console.log('✅ QR Code ready - check /qr endpoint');
            } catch (qrError) {
                console.error('❌ QR generation error:', qrError.message);
            }
            
            if (qrAttempts >= maxQRAttempts) {
                console.log('⚠️ Max QR attempts reached - clearing session');
                clearSession();
                qrAttempts = 0;
                setTimeout(() => initializeWhatsApp(), 10000);
            }
        }

        if (connection === 'close') {
            appState.whatsappConnected = false;
            appState.whatsappInitializing = false;
            qrCodeBase64 = null;
            
            const shouldReconnect = (lastDisconnect?.error instanceof Boom)
                ? lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut
                : true;

            console.log('❌ Connection closed:', lastDisconnect?.error?.message);
            
            if (shouldReconnect) {
                setTimeout(() => {
                    console.log('🔄 Reconnecting...');
                    initializeWhatsApp();
                }, 10000);
            } else {
                console.log('❌ Not reconnecting - logged out');
                clearSession();
            }
        } else if (connection === 'open') {
            console.log('✅ WhatsApp connected successfully!');
            appState.whatsappConnected = true;
            appState.whatsappInitializing = false;
            appState.initializationComplete = true;
            qrCodeBase64 = null;
            
            // Backup session
            setTimeout(async () => {
                const sessionManager = new CloudSessionManager();
                await sessionManager.uploadSession();
            }, 5000);
            
            if (sock.user) {
                console.log(`👤 Connected as: ${sock.user.name || sock.user.id}`);
            }
        } else if (connection === 'connecting') {
            console.log('🔄 Connecting to WhatsApp...');
        }
    });

    sock.ev.on('creds.update', async () => {
        try {
            if (saveCreds) {
                await saveCreds();
                console.log('💾 Credentials saved');
            }
        } catch (error) {
            console.error('❌ Save credentials error:', error.message);
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        try {
            if (!m?.messages?.length) return;
            
            const msg = m.messages[0];
            if (!msg || msg.key.fromMe || m.type !== 'notify') return;
            
            const messageText = msg.message?.conversation || msg.message?.extendedTextMessage?.text;
            if (!messageText || !msg.key.remoteJid) return;
            
            console.log('📩 New message:', messageText.substring(0, 30) + '...');
            
            await saveMessageToFirebase(msg.key.remoteJid, messageText, 'received');
            await processMessage(msg.key.remoteJid, messageText, msg.key.id);
            
        } catch (error) {
            console.error('❌ Message processing error:', error.message);
        }
    });
}

// PROCESS INCOMING MESSAGE
async function processMessage(from, message, messageId) {
    try {
        // Check for special commands
        const lowerMessage = message.toLowerCase().trim();
        
        if (lowerMessage === '!status') {
            const statusMsg = `🤖 Bot Status: ✅ Online\n☁️ Cloud Run: ${CONFIG.isCloudRun ? 'Yes' : 'No'}\n🔥 Firebase: ${appState.firebaseConnected ? 'Connected' : 'Disconnected'}\n📱 WhatsApp: Connected\n⏰ Uptime: ${Math.floor((new Date() - appState.startTime) / 1000)}s`;
            await sendWhatsAppMessage(from, statusMsg);
            return;
        }
        
        // Forward to backend
        await forwardToBackend(from, message, messageId);
        
    } catch (error) {
        console.error('❌ Process message error:', error.message);
    }
}

// FORWARD TO BACKEND
async function forwardToBackend(from, message, messageId) {
    try {
        const webhookUrl = process.env.FASTAPI_WEBHOOK_URL || 'https://law-firm-backend-936902782519-936902782519.us-central1.run.app/api/v1/whatsapp/webhook';
        
        const payload = { 
            from, 
            message, 
            messageId: messageId || 'unknown', 
            sessionId: `whatsapp_${from.replace('@s.whatsapp.net', '')}`,
            timestamp: new Date().toISOString(), 
            platform: 'whatsapp',
            cloud_run: true
        };

        console.log('🔗 Forwarding to backend...');
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'User-Agent': 'WhatsApp-Bot-CloudRun/1.0'
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const responseText = await response.text();
            
            let responseData;
            try {
                responseData = JSON.parse(responseText);
            } catch (parseError) {
                console.error('❌ Backend response parse error:', parseError.message);
                return;
            }
            
            console.log('✅ Backend responded');
            
            // Check response
            if (responseData?.hasOwnProperty('response')) {
                if (responseData.response && typeof responseData.response === 'string' && responseData.response.trim() !== '') {
                    await sendWhatsAppMessage(from, responseData.response);
                    await saveMessageToFirebase(from, responseData.response, 'sent');
                    console.log('✅ Message sent to user');
                } else {
                    console.log('🔇 Empty response - user not authorized');
                }
            } else {
                console.warn('⚠️ Backend response missing response field');
            }
        } else {
            console.error('❌ Backend error:', response.status);
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.error('❌ Backend timeout');
        } else {
            console.error('❌ Backend error:', error.message);
        }
    }
}

// SEND WHATSAPP MESSAGE
async function sendWhatsAppMessage(to, message) {
    try {
        if (!appState.whatsappConnected || !sock || !to || !message) {
            throw new Error('Invalid parameters or WhatsApp not connected');
        }

        const jid = to.includes('@s.whatsapp.net') ? to : `${to}@s.whatsapp.net`;
        
        console.log('Sending message...');
        
        const result = await sock.sendMessage(jid, { text: String(message) });
        
        if (result && result.key && result.key.id) {
            console.log('Message sent successfully');
            return result.key.id;
        } else {
            return 'sent';
        }
        
    } catch (error) {
        console.error('Send message error:', error.message);
        throw error;
    }
}

// CLEAR SESSION
function clearSession() {
    try {
        if (fs.existsSync(CONFIG.sessionPath)) {
            fs.rmSync(CONFIG.sessionPath, { recursive: true, force: true });
        }
        console.log('✅ Session cleared');
    } catch (error) {
        console.error('❌ Clear session error:', error.message);
    }
}

// Monitoramento de memória para Cloud Run
setInterval(() => {
    const memUsage = process.memoryUsage();
    if (memUsage.heapUsed > CONFIG.maxMemoryUsage) {
        console.warn('⚠️ High memory usage:', Math.round(memUsage.heapUsed / 1024 / 1024) + 'MB');
    }
}, 60000);

// GRACEFUL SHUTDOWN
process.on('SIGTERM', () => {
    console.log('📴 SIGTERM received - graceful shutdown');
    if (server) {
        server.close(() => {
            process.exit(0);
        });
    } else {
        process.exit(0);
    }
});

process.on('SIGINT', () => {
    console.log('📴 SIGINT received - graceful shutdown');
    process.exit(0);
});

// ERROR HANDLING
process.on('uncaughtException', (error) => {
    console.error('❌ Uncaught Exception:', error.message);
    appState.lastError = `Uncaught: ${error.message}`;
    setTimeout(() => process.exit(1), 2000);
});

process.on('unhandledRejection', (reason) => {
    console.error('❌ Unhandled Rejection:', reason);
    appState.lastError = `Unhandled: ${reason}`;
});

console.log('✅ WhatsApp Bot Cloud Run initialization complete')