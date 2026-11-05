import { request } from '../lib/api';
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

// Where backend runs


// `onLogin` is a function passed down from App. We call it with the token.
function Auth({ onLogin }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  // Ask backend for login token
  async function getToken(emailValue, passwordValue) {
    const data = await request('/token', {
      method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: emailValue, password: passwordValue }),
    });
    return data.access_token;
  }

  // Runs when form is submitted (log in or sign up)
  async function handleSubmit(e) {
    e.preventDefault(); // Stops browser from reloading page
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (isRegistering) {
        await request('/register', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, email, password }),
        });
      }
      const token = await getToken(email, password);
      await onLogin(token);
      navigate("/");
    } catch (err) {
      setError(err instanceof TypeError ? "Unable to reach NOSH. Check that the backend is running." : err.message);
    } finally { setBusy(false); }
  }

  return (
    <main className="auth">
      <Link to="/" className="auth-back">← Back</Link>
      
      {/* Animated Blob */}
      <div className="blob" aria-hidden="true">
        <span className="eye" /><span className="eye" />
      </div>

      <h1>{isRegistering ? "Create account" : "Welcome back"}</h1>

      <form onSubmit={handleSubmit} className="auth-form">
        {/* Username needed when sign up */}
        {isRegistering && (
          <input
            required aria-label="Username" autoComplete="username" maxLength={100} placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        )}
        <input
          type="email"
          required aria-label="Email" autoComplete="email" placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          required aria-label="Password" autoComplete={isRegistering ? "new-password" : "current-password"} placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {/* Shown when error message */}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Please wait…" : isRegistering ? "Sign up" : "Sign in"}
        </button>
      </form>

      {/* Switch between log in and sign up page */}
      <button className="auth-switch" disabled={busy} onClick={() => setIsRegistering(!isRegistering)}>
        {isRegistering ? "Have an account? Sign in" : "New here? Create an account"}
      </button>
    </main>
  );
}

export default Auth;