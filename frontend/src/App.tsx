import './App.css'

function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="eyebrow">Repository intelligence</p>
        <h1>CodeLens</h1>
        <p className="intro">
          Upload a local repository to understand its code and review changes with grounded context.
        </p>
      </header>

      <section className="workspace-card" aria-labelledby="workspace-heading">
        <h2 id="workspace-heading">Start a temporary session</h2>
        <p className="muted">
          Repository upload, indexing, Q&amp;A, and code review will be available as the next workflow
          tickets are implemented.
        </p>
        <button type="button" disabled>
          Create session
        </button>
      </section>
    </main>
  )
}

export default App
