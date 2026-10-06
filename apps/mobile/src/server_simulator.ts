import express from 'express';
import path from 'path';
import os from 'os';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.resolve(__dirname, '../public')));

app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', app: 'Podcast AI Camera Mobile Simulator' });
});

// Helper to get local network IP address
function getLocalIpAddress() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name] || []) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

const HOST = '0.0.0.0';
const localIp = getLocalIpAddress();

app.listen(Number(PORT), HOST, () => {
  console.log('==================================================================');
  console.log(`[+] MOBILE APPLICATION SERVER RUNNING AT:`);
  console.log(`    - Local Computer: http://localhost:${PORT}`);
  console.log(`    - On Your Phone:  http://${localIp}:${PORT}`);
  console.log('==================================================================');
  console.log(`Open http://${localIp}:${PORT} on your mobile phone's browser!`);
});
