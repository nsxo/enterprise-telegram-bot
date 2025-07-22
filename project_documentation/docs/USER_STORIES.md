
# User Stories

This document outlines key features from the perspective of the users and administrators.

---

### Story: New User Onboarding

- **As a** new user,
- **I want to** send the `/start` command and see a simple, clean welcome message with a single "Start" button,
- **So that** I am not overwhelmed and have a clear next step to see what the bot offers.

---

### Story: Checking Balance

- **As a** user with credits,
- **I want to** type `/balance`,
- **So that** I can instantly see my remaining credits with a visual progress bar, helping me decide if I need to buy more soon.

---

### Story: Admin Responding to a User

- **As an** administrator,
- **I want to** simply type a reply inside a user's dedicated topic in the admin group,
- **So that** the bot automatically and privately sends my message to the correct user without me needing to use any special commands. I want to see a '✅' reaction on my message to know it was sent successfully.

---

### Story: Handling a New User Message

- **As an** administrator,
- **When a** new user sends their first message to the bot,
- **I want** the system to automatically create a new, neatly named topic for them in the admin group, pin a card with their key details at the top, and forward their message into it,
- **So that** I have a fully organized and contextualized support ticket system from the very first interaction.

---

### Story: Managing Payment Methods

- **As a** user who has made a purchase,
- **I want to** type `/billing`,
- **So that** I receive a secure, private link to a Stripe-hosted page where I can view, add, or remove my saved credit cards.
