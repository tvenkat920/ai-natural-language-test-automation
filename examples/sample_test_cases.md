# Sample Natural-Language Test Cases

This document provides representative English test prompts covering varied web applications, authentication flows, form interactions, and assertion types supported by **AI Natural Language Test Automation**.

---

## 1. Authentication Flow (With Credentials)

```bash
python -m app \
  --url "https://the-internet.herokuapp.com/login" \
  --test "Open login page, enter username 'tomsmith' and password 'SuperSecretPassword!', click Login, and verify 'You logged into a secure area!' is visible" \
  --credentials '{"username":"tomsmith","password":"SuperSecretPassword!"}'
```

**Expected Flow:**
1. `navigate`: `https://the-internet.herokuapp.com/login`
2. `fill`: target `Username`, value: `tomsmith`
3. `fill`: target `Password`, value: `SuperSecretPassword!`
4. `click`: target `Login` button
5. `assert_visible`: text `You logged into a secure area!`
6. `screenshot`: captures evidence

---

## 2. Missing Credentials Detection (Clarification Flow)

```bash
python -m app \
  --url "https://example-enterprise.com/portal" \
  --test "Open the portal, log in as customer, and check dashboard"
```

**Expected Flow:**
- The engine identifies that customer credentials are required but none were supplied.
- Stops safely before opening browser.
- Returns status `NEEDS_CLARIFICATION`.
- Prompts user: `"This test requires login credentials. Please provide username and password via --credentials or interactive mode."`

---

## 3. E-Commerce / Search Flow

```bash
python -m app \
  --url "https://books.toscrape.com" \
  --test "Open the bookstore catalogue and verify the page title contains 'All products' and books are visible"
```

**Expected Flow:**
1. `navigate`: `https://books.toscrape.com`
2. `assert_title`: expected contains `All products`
3. `assert_visible`: content body / grid
4. `screenshot`: captures evidence

---

## 4. Generic Smoke Verification

```bash
python -m app \
  --url "https://example.com" \
  --test "Open the website and verify its title contains 'Example Domain' and header is visible"
```

---

## 5. Interactive Form Submission

```bash
python -m app \
  --url "http://127.0.0.1:8000/sample_page.html" \
  --test "Open the sample page, fill in first name 'Alice', email 'alice@example.com', select country 'United States', check the terms, click Submit Form, and verify the success message"
```

