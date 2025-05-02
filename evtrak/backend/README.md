# EVTrak Backend

This is the backend API for EVTrak, built with Cloudflare Workers.

## Features

- Tesla OAuth integration
- Vehicle tracking
- Trip recording
- OReGO refund form generation
- Batch processing for annual submissions

## Development

To run locally:

```bash
npm install
npx wrangler dev
```

## Deployment

Deployment is handled automatically via GitHub Actions when changes are pushed to the main branch.

## Environment Variables

- `TESLA_CLIENT_ID`: Tesla API client ID
- `TESLA_CLIENT_SECRET`: Tesla API client secret
- `JWT_SECRET`: Secret for JWT token generation
- `ADMIN_API_KEY`: API key for admin endpoints

## Database

Uses Cloudflare D1 (SQLite) for data storage.