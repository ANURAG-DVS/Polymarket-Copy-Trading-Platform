# Stripe Integration Guide

## Overview

Complete Stripe integration for subscription payments with three tiers: Free, Pro, and Enterprise.

## Setup

### 1. Install Stripe

```bash
pip install stripe
```

### 2. Create Stripe Account

1. Sign up at https://stripe.com
2. Get API keys from Dashboard → Developers → API keys

### 3. Create Products and Prices

**In Stripe Dashboard:**

1. Go to Products → Add Product
2. Create products:
   - **Pro Plan**: $29/month
   - **Enterprise Plan**: $99/month

3. Copy Price IDs

### 4. Configure Environment Variables

```bash
# .env.production
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_ENTERPRISE_PRICE_ID=price_...

# .env.development (Test Mode)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_ENTERPRISE_PRICE_ID=price_...
```

### 5. Set Up Webhooks

**In Stripe Dashboard:**

1. Go to Developers → Webhooks → Add endpoint
2. Endpoint URL: `https://api.polymarket-copy.com/api/v1/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`

4. Copy webhook secret to `STRIPE_WEBHOOK_SECRET`

### 6. Run Migration

```bash
cd backend
alembic upgrade head
```

## API Endpoints

### Create Checkout Session

**Request:**
```http
POST /api/v1/subscription/checkout
Authorization: Bearer <token>
Content-Type: application/json

{
  "tier": "PRO",
  "success_url": "https://polymarket-copy.com/success",
  "cancel_url": "https://polymarket-copy.com/canceled"
}
```

**Response:**
```json
{
  "session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

### Create Customer Portal Session

**Request:**
```http
POST /api/v1/subscription/portal
Authorization: Bearer <token>
Content-Type: application/json

{
  "return_url": "https://polymarket-copy.com/settings"
}
```

**Response:**
```json
{
  "url": "https://billing.stripe.com/session/..."
}
```

### Get Subscription Status

**Request:**
```http
GET /api/v1/subscription/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "tier": "PRO",
  "status": "active",
  "stripe_customer_id": "cus_...",
  "stripe_subscription_id": "sub_..."
}
```

## Frontend Integration

### React Example

```typescript
// UpgradeButton.tsx
import { useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export function UpgradeButton({ tier }: { tier: 'PRO' | 'ENTERPRISE' }) {
  const [loading, setLoading] = useState(false);

  const handleUpgrade = async () => {
    setLoading(true);
    
    try {
      // Create checkout session
      const response = await fetch('/api/v1/subscription/checkout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tier,
          success_url: `${window.location.origin}/subscription/success?session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/subscription/canceled`
        })
      });
      
      const { url } = await response.json();
      
      // Redirect to Stripe Checkout
      window.location.href = url;
    } catch (error) {
      console.error('Failed to create checkout session:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleUpgrade} disabled={loading}>
      {loading ? 'Loading...' : `Upgrade to ${tier}`}
    </button>
  );
}
```

### Customer Portal

```typescript
// ManageBillingButton.tsx
export function ManageBillingButton() {
  const handleManage = async () => {
    const response = await fetch('/api/v1/subscription/portal', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        return_url: window.location.href
      })
    });
    
    const { url } = await response.json();
    window.location.href = url;
  };

  return (
    <button onClick={handleManage}>
      Manage Billing
    </button>
  );
}
```

## Webhook Testing

### Local Testing with Stripe CLI

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local endpoint
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe

# Test webhook
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_failed
```

### Manual Testing

```bash
# Use Stripe test cards
# Success: 4242 4242 4242 4242
# Decline: 4000 0000 0000 0002
# 3D Secure: 4000 0027 6000 3184
```

## Payment Flow

### Successful Payment

```
1. User clicks "Upgrade to Pro"
   ↓
2. Frontend calls POST /api/subscription/checkout
   ↓
3. Backend creates Stripe checkout session
   ↓
4. User redirected to Stripe Checkout
   ↓
5. User enters payment details
   ↓
6. Stripe processes payment
   ↓
7. Stripe sends webhook: checkout.session.completed
   ↓
8. Backend updates user.subscription_tier = PRO
   ↓
9. Backend updates user.subscription_status = active
   ↓
10. User redirected to success_url
   ↓
11. Frontend shows success message
   ↓
12. Pro features activated immediately
```

### Failed Payment

```
1. Payment fails (card declined, etc.)
   ↓
2. Stripe sends webhook: invoice.payment_failed
   ↓
3. Backend updates user.subscription_status = past_due
   ↓
4. Stripe retries payment (configurable)
   ↓
5. If all retries fail:
   - Webhook: customer.subscription.deleted
   - Backend: user.subscription_tier = FREE
   - Send email notification
```

## Subscription States

### Status Values

- `active` - Subscription is active and paid
- `past_due` - Payment failed, will retry
- `canceled` - Subscription canceled by user
- `unpaid` - Payment failed, no more retries
- `incomplete` - Initial payment not yet successful

### State Transitions

```
       active
         ↓
    past_due (payment failed)
         ↓
    unpaid (retry failed)
         ↓
    canceled (downgrade to FREE)
```

## Customer Portal Features

Users can manage their subscription in the Stripe Customer Portal:

- Update payment method
- View invoices
- Download receipts
- Cancel subscription
- Reactivate subscription
- Update billing address

## Handling Edge Cases

### Double Payment Prevention

```python
# Webhook is idempotent
# Stripe sends event.id which can be stored
# to prevent duplicate processing

if await is_event_processed(event.id):
    return {"status": "already_processed"}
```

### Subscription Overlap

```python
# User upgrades from Pro to Enterprise
# Stripe handles proration automatically
# No action needed in webhook handler
```

### Immediate Downgrade vs. End of Period

```python
# In Stripe Dashboard:
# Settings → Billing → Subscriptions
# - "Cancel at period end" (keep Pro until month ends)
# - "Cancel immediately" (downgrade to FREE now)
```

## Testing Scenarios

### Test Mode Cards

```
Success: 4242 4242 4242 4242
Decline: 4000 0000 0000 0002
Insufficient funds: 4000 0000 0000 9995
Requires 3DS: 4000 0027 6000 3184
```

### Test Webhook Events

```bash
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
stripe trigger invoice.payment_failed
stripe trigger invoice.payment_succeeded
```

## Production Checklist

- [ ] Replace test API keys with live keys
- [ ] Update webhook endpoint URL
- [ ] Test live payment flow
- [ ] Configure email notifications
- [ ] Set up Stripe Radar for fraud prevention
- [ ] Enable 3D Secure authentication
- [ ] Configure retry logic for failed payments
- [ ] Set up billing alerts in Stripe
- [ ] Add tax collection (if applicable)
- [ ] Review Stripe fees structure

## Monitoring

### Key Metrics

- Successful checkouts
- Failed payments
- Churn rate
- MRR (Monthly Recurring Revenue)
- Subscription upgrades/downgrades

### Stripe Dashboard

- Dashboard → Home (overview)
- Payments → All payments
- Customers → All customers
- Billing → Subscriptions
- Developers → Webhooks (delivery status)

## Security Best Practices

1. **Never expose secret keys** - Only use publishable key in frontend
2. **Verify webhooks** - Always verify signature
3. **Use HTTPS** - Webhooks must use HTTPS in production
4. **Store minimal data** - Don't store card details
5. **Handle errors gracefully** - Log but don't expose details
6. **Implement rate limiting** - Prevent abuse
7. **Monitor webhook delivery** - Set up alerts for failures

## Support

**Documentation:**
- https://stripe.com/docs
- https://stripe.com/docs/billing

**Test Mode:**
- All test data is isolated
- No real charges
- Test cards: https://stripe.com/docs/testing

**Support:**
- Stripe Support: https://support.stripe.com
- Status: https://status.stripe.com
