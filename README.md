
# NVIDIA NIM Model Dashboard

A clean, professional, and mobile-responsive dashboard to check the status, speed, and availability of NVIDIA NIM models.

## Features

- 🔑 **API Key Management**: Save and clear your NVIDIA NIM API key securely (stored in browser localStorage).
- 🔄 **Dynamic Model Discovery**: Automatically fetches the latest list of models from NVIDIA NIM (no hardcoded list).
- ⚡ **Real-time Health Check**: Tests each model with a minimal request to measure response time and tokens/sec.
- 📊 **Advanced Sorting & Filtering**: Sort by speed, response time, or name. Filter by success/failure status.
- 📱 **Mobile Responsive**: Optimized for both desktop and mobile devices.
- 🎨 **Clean UI**: Professional design without excessive AI-style effects.

## How to Use

1. **Enter your NVIDIA NIM API Key** in the input field and click "Save".
2. Click **"Check All Models"** to start the health check.
3. View the results in the table, sorted and filtered as needed.

## Deployment

This app is deployed on Vercel. To run locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## License

MIT
