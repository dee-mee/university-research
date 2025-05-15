# Developer Guide

## Project Structure

```
research_portal/
├── research_portal/           # Project root
│   ├── settings/             # Django settings
│   ├── urls.py              # URL routing
│   ├── wsgi.py              # WSGI config
│   └── asgi.py              # ASGI config
├── maps/                     # Main app
│   ├── models/              # Database models
│   ├── views/               # Views
│   ├── api_views/           # API views
│   ├── serializers/         # REST serializers
│   ├── consumers/           # WebSocket consumers
│   ├── tasks/               # Background tasks
│   ├── utils/               # Utility functions
│   ├── templates/           # HTML templates
│   ├── static/              # Static files
│   └── migrations/          # Database migrations
├── requirements/            # Python dependencies
└── docs/                    # Documentation
```

## Development Setup

### 1. Prerequisites
- Python 3.8+
- Node.js 14+
- PostgreSQL 12+
- Redis
- Git

### 2. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements/dev.txt
npm install
```

### 4. Configure Environment
Create a `.env` file:
```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Code Style and Standards

### Python
- Follow PEP 8 style guide
- Use type hints
- Write docstrings
- Keep lines under 80 characters
- Use meaningful variable names

### JavaScript
- Use ES6+ features
- Follow Airbnb style guide
- Use React hooks
- Write JSDoc comments

### CSS
- Use CSS Modules
- Follow BEM methodology
- Use CSS variables
- Keep selectors specific

## Development Workflow

### 1. Feature Development
1. Create a new branch
2. Write tests first
3. Implement feature
4. Write documentation
5. Submit pull request

### 2. Testing
- Unit tests: `pytest`
- Integration tests: `pytest`
- Frontend tests: `Jest`
- E2E tests: `Cypress`

### 3. Code Review
- Follow review checklist
- Check for security issues
- Verify test coverage
- Review documentation

## Database Structure

### Main Tables
1. FieldDevice
```sql
CREATE TABLE field_device (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    device_type_id INTEGER REFERENCES device_type(id),
    location GEOGRAPHY(POINT, 4326),
    status VARCHAR(20) NOT NULL,
    battery_level FLOAT,
    signal_strength INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

2. FieldDataRecord
```sql
CREATE TABLE field_data_record (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES field_device(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    data JSONB NOT NULL,
    location GEOGRAPHY(POINT, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);
```

## API Development

### REST API
- Use Django REST Framework
- Implement proper authentication
- Use serializers for data validation
- Implement rate limiting
- Add proper error handling

### WebSocket API
- Use Django Channels
- Implement proper connection handling
- Add message validation
- Implement reconnection logic
- Add proper error handling

## Security Best Practices

### Authentication
- Use token-based authentication
- Implement proper password hashing
- Use secure session management
- Implement CSRF protection
- Add rate limiting

### Data Protection
- Encrypt sensitive data
- Implement proper input validation
- Use secure headers
- Add CSRF protection
- Implement XSS protection

## Performance Optimization

### Database
- Use proper indexes
- Implement connection pooling
- Use query optimization
- Add caching layer
- Implement proper pagination

### Frontend
- Use code splitting
- Implement lazy loading
- Use proper caching
- Optimize images
- Minimize bundle size

## Deployment

### Production Checklist
1. Security
   - Enable HTTPS
   - Configure proper headers
   - Set up firewall rules
   - Configure rate limiting

2. Performance
   - Set up caching
   - Configure database
   - Set up load balancing
   - Configure CDN

3. Monitoring
   - Set up logging
   - Configure error tracking
   - Set up performance monitoring
   - Configure alerting

## Contributing

### Guidelines
1. Follow coding standards
2. Write tests
3. Update documentation
4. Create meaningful commit messages
5. Submit well-documented PRs

### Pull Request Process
1. Create a branch
2. Add tests
3. Update documentation
4. Submit PR
5. Get review
6. Merge changes

## Version Control

### Branching Strategy
- `main`: Production code
- `develop`: Development code
- `feature/*`: New features
- `hotfix/*`: Critical fixes
- `release/*`: Release preparation

### Commit Messages
```
feat: Add new feature
fix: Fix bug
perf: Improve performance
docs: Update documentation
style: Code style changes
refactor: Code refactoring
test: Add tests
chore: Maintenance tasks
```

## Troubleshooting Common Issues

### 1. Database Connection
- Verify database credentials
- Check connection string
- Verify database is running
- Check firewall rules

### 2. WebSocket Connection
- Verify Redis is running
- Check WebSocket configuration
- Verify network connectivity
- Check browser console

### 3. API Issues
- Check request format
- Verify authentication
- Check rate limits
- Review API logs

## Best Practices

### Code Organization
1. Keep components small
2. Use proper naming
3. Follow DRY principle
4. Write maintainable code
5. Add proper documentation

### Testing
1. Write tests first
2. Test edge cases
3. Verify error handling
4. Check performance
5. Test security

### Security
1. Validate all inputs
2. Use proper authentication
3. Implement rate limiting
4. Use secure headers
5. Follow OWASP guidelines

## Resources

### Documentation
- Django documentation
- React documentation
- PostgreSQL documentation
- Redis documentation

### Tools
- PyCharm/VS Code
- Docker
- Git
- Postman

### Learning Resources
- Django REST Framework tutorial
- React documentation
- PostgreSQL tutorials
- WebSocket tutorials

## License
This project is licensed under the MIT License. For more information, see the LICENSE file.
