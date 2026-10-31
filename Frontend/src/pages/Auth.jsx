import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

// Where backend runs
const API = `http://${window.location.hostname}:8000`;

// FastAPi sends errors which get turn into text
function errorText(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
  return "Something went wrong";
}

// `onLogin` is a function passed down from App. We call it with the token.
function Auth({ onLogin }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  // Ask backend for login token
  async function getToken(emailValue, passwordValue) {
    const response = await fetch(`${API}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: emailValue, password: passwordValue }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(errorText(data.detail));
    return data.access_token;
  }

  // Runs when form is submitted (log in or sign up)
  async function handleSubmit(e) {
    e.preventDefault(); // Stops browser from reloading page
    setError("");
    try {
      if (isRegistering) {
        const response = await fetch(`${API}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email, password }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(errorText(data.detail));
      }
      const token = await getToken(email, password);
      await onLogin(token);
      navigate("/");
    } catch (err) {
      setError(err.message || "Can't reach the server");
    }
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
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        )}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {/* Shown when error message */}
        {error && <p className="auth-error">{error}</p>}
        <button type="submit" className="btn-primary">
          {isRegistering ? "Sign up" : "Sign in"}
        </button>
      </form>

      {/* Switch between log in and sign up page */}
      <button className="auth-switch" onClick={() => setIsRegistering(!isRegistering)}>
        {isRegistering ? "Have an account? Sign in" : "New here? Create an account"}
      </button>
    </main>
  );
}

export default Auth;