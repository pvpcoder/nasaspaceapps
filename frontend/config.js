// Where the dashboard finds the backend.
// - On localhost (or Render itself) the backend is the same server, so leave it blank.
// - On GitHub Pages, point it at your Render URL (no trailing slash).
window.FLAMEWATCH_API = location.hostname.endsWith("github.io")
  ? "https://flamewatch.onrender.com"   // <-- change if Render gives you a different URL
  : "";
