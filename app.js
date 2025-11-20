const express = require('express');
const app = express();
const VERSION = process.env.VERSION || 'unknown';

app.get('/', (req, res) => {
  res.json({
    app: 'WrkTalk Test',
    version: VERSION,
    message: `Running version ${VERSION}`,
    timestamp: new Date().toISOString()
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', version: VERSION });
});

app.listen(3000, () => {
  console.log(`App version ${VERSION} listening on port 3000`);
});
