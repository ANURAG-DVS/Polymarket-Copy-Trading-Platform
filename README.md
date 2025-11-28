# Polymarket Copy Trading Platform

A full-stack platform that enables users to automatically mirror trades from successful Polymarket traders. Built with real-time blockchain monitoring, automated trade execution, and multi-interface support (Web + Telegram).

## 🚀 Features

- **Real-time Trade Monitoring**: Track on-chain Polymarket trades as they happen
- **Automated Copy Trading**: Execute trades automatically when followed traders make moves
- **Leaderboard System**: Rank traders by performance metrics (win rate, ROI, Sharpe ratio)
- **Multi-Interface Access**: Web dashboard and Telegram bot
- **Risk Management**: Configurable position sizing, slippage protection, daily limits
- **Secure Key Storage**: Multi-layer encryption for API keys and private keys
- **Performance Analytics**: Detailed statistics and historical performance tracking

## 🏗️ Architecture

### Tech Stack

- **Backend**: FastAPI (Python 3.11) with async/await
- **Database**: PostgreSQL + TimescaleDB for time-series data
- **Cache & Queue**: Redis + Celery for distributed task processing
- **Blockchain**: Web3.py for Polygon network interaction
- **Frontend**: Next.js 14 (App Router) + TypeScript
- **Telegram Bot**: python-telegram-bot
- **Deployment**: Docker + Docker Compose

### System Components

```
┌─────────────┐     ┌──────────────┐
│   Web App   │────▶│  Backend API │
└─────────────┘     └──────┬───────┘
                           │
┌─────────────┐            │
│Telegram Bot │────────────┤
└─────────────┘            │
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │  TimescaleDB │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    Redis     │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Blockchain │  │   Trade      │  │Notifications │
│   Monitor    │  │   Executor   │  │   Worker     │
└──────────────┘  └──────────────┘  └──────────────┘
        │
        ▼
┌──────────────┐
│   Polygon    │
│   Network    │
└──────────────┘
```

## 📋 Prerequisites

- **Docker** and **Docker Compose** (20.10+)
- **Node.js** 18+ (for local frontend development)
- **Python** 3.11+ (for local backend development)
- **PostgreSQL** 15+ (if not using Docker)
- **Redis** 7+ (if not using Docker)

## 🔧 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/polymarket-copy-trading-platform.git
cd polymarket-copy-trading-platform
```

### 2. Environment Setup

Copy the example environment files and fill in your values:

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env

# Telegram Bot
cp telegram-bot/.env.example telegram-bot/.env
```

**Critical Environment Variables:**

```bash
# Backend (.env)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
MASTER_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET_KEY=$(openssl rand -hex 32)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Frontend (.env)
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=your_walletconnect_id
```

### 3. Start Services with Docker

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (with TimescaleDB) on port 5432
- Redis on port 6379
- Backend API on port 8000
- Frontend on port 3000
- Celery workers (blockchain, trades, notifications)
- Flower (Celery monitoring) on port 5555
- Telegram bot

### 4. Initialize Database

```bash
# Run migrations
docker-compose exec backend alembic upgrade head
```

### 5. Access the Platform

- **Web App**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Celery Monitor**: http://localhost:5555

## 🛠️ Development

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### Telegram Bot Development

```bash
cd telegram-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run bot
python -m bot.main
```

## 📁 Project Structure

```
polymarket-copy-trading-platform/
├── backend/                  # FastAPI Backend
│   ├── app/
│   │   ├── api/             # API endpoints
│   │   ├── core/            # Core configuration
│   │   ├── db/              # Database models
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── workers/         # Celery tasks
│   ├── alembic/             # Database migrations
│   ├── tests/               # Tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                 # Next.js Frontend
│   ├── src/
│   │   ├── app/            # App router pages
│   │   ├── components/     # React components
│   │   ├── lib/            # Utilities
│   │   ├── hooks/          # Custom hooks
│   │   └── types/          # TypeScript types
│   ├── public/             # Static assets
│   ├── package.json
│   └── Dockerfile
│
├── telegram-bot/            # Telegram Bot
│   ├── bot/
│   │   ├── handlers/       # Command handlers
│   │   ├── keyboards/      # Inline keyboards
│   │   └── utils/          # Helper functions
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── infrastructure/          # Infrastructure configs
│   ├── docker/
│   │   ├── init-db.sql    # Database initialization
│   │   └── nginx.conf     # Nginx config
│   └── scripts/           # Utility scripts
│
├── .github/workflows/       # CI/CD pipelines
├── docker-compose.yml
└── README.md
```

## 🔐 Security Considerations

### API Key Storage

- **Multi-layer encryption**: Application-level (Fernet) + database-level (pgcrypto)
- **Environment-based master key**: Never committed to version control
- **Key rotation**: Implement 90-day rotation policy
- **Audit logging**: All key access attempts logged

### Trade Security

- **Local transaction signing**: Private keys never sent over network
- **Transaction simulation**: Using Tenderly before execution
- **Slippage protection**: Configurable max slippage (default 1%)
- **Rate limiting**: Per-user and per-endpoint limits
- **2FA support**: For sensitive operations

### Network Security

- **TLS/SSL**: All communication encrypted
- **CORS**: Whitelist trusted origins only
- **Security headers**: XSS, clickjacking protection
- **Webhook verification**: Validate Telegram signatures

## 📊 Database Schema

Key tables:

- `users`: User accounts and profiles
- `api_keys`: Encrypted API keys and private keys
- `trades`: Historical trade data (TimescaleDB hypertable)
- `copy_relationships`: User-trader copy configurations
- `trader_stats`: Aggregated trader performance metrics
- `notifications`: User notifications

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

### Frontend Tests

```bash
cd frontend
npm run test
npm run test:coverage
```

## 🚀 Deployment

### Railway (Recommended for Hackathon)

1. Install Railway CLI:
```bash
npm install -g @railway/cli
```

2. Login and initialize:
```bash
railway login
railway init
```

3. Deploy services:
```bash
railway up
```

### Production Deployment

For production, use:
- **Backend**: AWS ECS / DigitalOcean App Platform
- **Database**: Managed PostgreSQL (RDS, DigitalOcean)
- **Redis**: ElastiCache, Upstash
- **Frontend**: Vercel
- **CDN**: Cloudflare

## 📝 API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/traders/leaderboard` - Get top traders
- `POST /api/v1/copy/follow` - Follow a trader
- `GET /api/v1/trades/history` - Get trade history
- `WS /ws/trades` - Real-time trade updates

## 🤖 Telegram Bot Commands

- `/start` - Initialize bot
- `/wallet` - Connect wallet
- `/follow <address>` - Follow a trader
- `/unfollow <address>` - Unfollow a trader
- `/leaderboard` - View top traders
- `/portfolio` - View your positions
- `/settings` - Configure copy trading settings

## 🔧 Configuration

### Environment Variables

See `.env.example` files in each service directory for all available options.

### Feature Flags

Toggle features via environment variables:

```bash
ENABLE_2FA=true
ENABLE_EMAIL_NOTIFICATIONS=false
ENABLE_TELEGRAM_NOTIFICATIONS=true
ENABLE_TRADE_EXECUTION=true
```

## 📈 Monitoring

### Logs

```bash
# View backend logs
docker-compose logs -f backend

# View all services
docker-compose logs -f
```

### Celery Monitoring

Access Flower at http://localhost:5555 to monitor:
- Active workers
- Task success/failure rates
- Queue lengths
- Worker health

### Database Performance

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d polymarket_copy

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables WHERE schemaname = 'public';
```

## 🐛 Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Ensure PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres
```

**Redis Connection Failed**
```bash
# Restart Redis
docker-compose restart redis
```

**Frontend Build Errors**
```bash
# Clear cache
cd frontend
rm -rf .next node_modules
npm install
npm run build
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Polymarket for the prediction market platform
- FastAPI and Next.js communities
- TimescaleDB for time-series optimization

## 📞 Support

- **Documentation**: [Link to your docs]
- **Issues**: [GitHub Issues](https://github.com/yourusername/polymarket-copy-trading-platform/issues)
- **Discord**: [Your Discord Server]
- **Email**: support@yourproject.com

---

**Built for Solana/Polygon Hackathon** 🏆
