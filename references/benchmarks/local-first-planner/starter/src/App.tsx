export default function App() {
  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">recursive-mode benchmark starter</p>
        <h1>Local First Planner</h1>
        <p>
          This placeholder app is intentionally incomplete. The benchmark agent
          is expected to turn it into the product described in
          <code> benchmark/00-requirements.md</code>.
        </p>
      </section>

      <section className="placeholder-grid">
        <article className="panel">
          <h2>Planner board</h2>
          <p>No work items yet.</p>
        </article>
        <article className="panel">
          <h2>Filters</h2>
          <p>Search, status, and priority controls should appear here.</p>
        </article>
        <article className="panel">
          <h2>Summary</h2>
          <p>Metrics and overdue indicators should appear here.</p>
        </article>
      </section>
    </main>
  );
}
