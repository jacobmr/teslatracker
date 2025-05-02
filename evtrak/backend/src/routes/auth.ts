import { nanoid } from 'nanoid';
import { sign, verify } from '../utils/jwt';
import { corsHeaders } from '../utils/cors';

// Tesla OAuth endpoints
const TESLA_AUTH_URL = 'https://auth.tesla.com/oauth2/v3/authorize';
const TESLA_TOKEN_URL = 'https://auth.tesla.com/oauth2/v3/token';

/**
 * Initiates Tesla OAuth flow
 */
export async function handleAuth(request: Request): Promise<Response> {
  const url = new URL(request.url);
  // Use the exact redirect URI that's configured in Tesla developer portal
  const redirectUri = 'https://www.evtrak.com/redirect';
  
  // Generate state parameter to prevent CSRF
  const state = nanoid();
  
  // Store state in KV for validation during callback
  const env = (request as any).env;
  await env.CACHE.put(`oauth_state:${state}`, 'true', { expirationTtl: 3600 });
  
  // Construct Tesla OAuth URL
  const teslaAuthUrl = new URL(TESLA_AUTH_URL);
  teslaAuthUrl.searchParams.append('client_id', env.TESLA_CLIENT_ID);
  teslaAuthUrl.searchParams.append('redirect_uri', redirectUri);
  teslaAuthUrl.searchParams.append('response_type', 'code');
  teslaAuthUrl.searchParams.append('scope', 'openid email offline_access vehicle_read');
  teslaAuthUrl.searchParams.append('state', state);
  
  // Redirect to Tesla auth page
  return new Response(null, {
    status: 302,
    headers: {
      ...corsHeaders,
      'Location': teslaAuthUrl.toString()
    }
  });
}

/**
 * Handles OAuth callback from Tesla
 */
export async function handleCallback(request: Request): Promise<Response> {
  const env = (request as any).env;
  const url = new URL(request.url);
  
  // Get code and state from query params
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const error = url.searchParams.get('error');
  // Use the exact redirect URI that's configured in Tesla developer portal
  const redirectUri = 'https://www.evtrak.com/redirect';
  
  // Handle errors from Tesla
  if (error) {
    console.error('Tesla OAuth error:', error);
    return redirectWithError('Authentication failed. Please try again.');
  }
  
  // Validate required params
  if (!code || !state) {
    return redirectWithError('Missing required parameters');
  }
  
  // Verify state parameter to prevent CSRF
  const validState = await env.CACHE.get(`oauth_state:${state}`);
  if (!validState) {
    return redirectWithError('Invalid state parameter');
  }
  
  // Clean up used state
  await env.CACHE.delete(`oauth_state:${state}`);
  
  try {
    // Exchange code for tokens
    const tokenResponse = await fetch(TESLA_TOKEN_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        grant_type: 'authorization_code',
        client_id: env.TESLA_CLIENT_ID,
        client_secret: env.TESLA_CLIENT_SECRET,
        code,
        redirect_uri: redirectUri
      })
    });
    
    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error('Token exchange error:', errorData);
      return redirectWithError('Failed to authenticate with Tesla');
    }
    
    const tokenData = await tokenResponse.json();
    
    // Get user info from token
    const userInfo = await getUserInfo(tokenData.access_token);
    
    // Check if user exists in our database
    const userId = userInfo.email.toLowerCase();
    const userExists = await checkUserExists(env.DB, userId);
    
    // Store tokens and create or update user
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = now + tokenData.expires_in;
    
    if (userExists) {
      // Update existing user
      await env.DB.prepare(`
        UPDATE users
        SET tesla_refresh_token = ?, tesla_token_expires_at = ?, updated_at = ?
        WHERE id = ?
      `)
      .bind(tokenData.refresh_token, expiresAt, now, userId)
      .run();
    } else {
      // Create new user
      await env.DB.prepare(`
        INSERT INTO users (id, email, full_name, tesla_refresh_token, tesla_token_expires_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `)
      .bind(userId, userInfo.email, userInfo.email, tokenData.refresh_token, expiresAt, now, now)
      .run();
      
      // Log the signup
      await env.DB.prepare(`
        INSERT INTO audit_logs (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
      `)
      .bind(nanoid(), userId, 'user_signup', 'Tesla OAuth signup', now)
      .run();
    }
    
    // Generate JWT for our frontend
    const jwt = await sign({
      sub: userId,
      email: userInfo.email,
      iat: now,
      exp: now + 86400 // 24 hours
    }, env.JWT_SECRET);
    
    // Redirect to frontend with token
    return new Response(null, {
      status: 302,
      headers: {
        ...corsHeaders,
        'Location': `https://www.evtrak.com/api/auth/success?token=${jwt}`
      }
    });
    
  } catch (error) {
    console.error('Error in OAuth callback:', error);
    return redirectWithError('Authentication failed. Please try again.');
  }
}

/**
 * Refreshes Tesla access token using refresh token
 */
export async function refreshToken(request: Request): Promise<Response> {
  const env = (request as any).env;
  
  try {
    // Verify JWT from authorization header
    const authHeader = request.headers.get('Authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
    
    const token = authHeader.split(' ')[1];
    const payload = await verify(token, env.JWT_SECRET);
    
    // Get user's refresh token from database
    const userResult = await env.DB.prepare(`
      SELECT tesla_refresh_token, tesla_token_expires_at
      FROM users
      WHERE id = ?
    `)
    .bind(payload.sub)
    .first();
    
    if (!userResult) {
      return new Response(JSON.stringify({ error: 'User not found' }), {
        status: 404,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
    
    // Check if token needs refreshing
    const now = Math.floor(Date.now() / 1000);
    if (userResult.tesla_token_expires_at > now + 300) {
      // Token still valid for more than 5 minutes
      return new Response(JSON.stringify({ message: 'Token still valid' }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
    
    // Refresh the token
    const tokenResponse = await fetch(TESLA_TOKEN_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        grant_type: 'refresh_token',
        client_id: env.TESLA_CLIENT_ID,
        client_secret: env.TESLA_CLIENT_SECRET,
        refresh_token: userResult.tesla_refresh_token
      })
    });
    
    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error('Token refresh error:', errorData);
      return new Response(JSON.stringify({ error: 'Failed to refresh token' }), {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
    
    const tokenData = await tokenResponse.json();
    
    // Update tokens in database
    const expiresAt = now + tokenData.expires_in;
    await env.DB.prepare(`
      UPDATE users
      SET tesla_refresh_token = ?, tesla_token_expires_at = ?, updated_at = ?
      WHERE id = ?
    `)
    .bind(tokenData.refresh_token, expiresAt, now, payload.sub)
    .run();
    
    return new Response(JSON.stringify({ 
      message: 'Token refreshed successfully',
      expires_at: expiresAt
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders
      }
    });
    
  } catch (error) {
    console.error('Error refreshing token:', error);
    return new Response(JSON.stringify({ error: 'Authentication failed' }), {
      status: 401,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders
      }
    });
  }
}

/**
 * Helper function to get user info from Tesla API
 */
async function getUserInfo(accessToken: string) {
  const response = await fetch('https://owner-api.teslamotors.com/api/1/users/me', {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });
  
  if (!response.ok) {
    throw new Error('Failed to get user info from Tesla');
  }
  
  const data = await response.json();
  return data.response;
}

/**
 * Helper function to check if user exists in database
 */
async function checkUserExists(db: any, userId: string): Promise<boolean> {
  const result = await db.prepare('SELECT 1 FROM users WHERE id = ?')
    .bind(userId)
    .first();
  
  return !!result;
}

/**
 * Helper function to redirect with error message
 */
function redirectWithError(message: string): Response {
  const encodedError = encodeURIComponent(message);
  return new Response(null, {
    status: 302,
    headers: {
      ...corsHeaders,
      'Location': `https://www.evtrak.com/back?error=${encodedError}`
    }
  });
}
