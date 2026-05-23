import { useEffect, useState } from "react";

interface ProjectEntry {
  id: string;
  name: string;
  description: string;
}

export default function ProjectSelector() {
  const [projects, setProjects] = useState<ProjectEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/graphs/index.json")
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: ProjectEntry[]) => {
        setProjects(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--color-root)] text-[var(--color-text-muted)]">
        Loading projects...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--color-root)] text-red-400">
        Failed to load projects: {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-root)] text-[var(--color-text)]">
      <div className="max-w-4xl mx-auto px-6 py-16">
        <header className="mb-12">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Knowledge Graph</h1>
          <p className="text-[var(--color-text-muted)]">
            Select a project to explore its architecture
          </p>
        </header>

        <div className="grid gap-4">
          {projects.map((project) => (
            <a
              key={project.id}
              href={`?project=${encodeURIComponent(project.id)}`}
              className="block p-6 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:bg-[var(--color-elevated)] transition-colors"
            >
              <h2 className="text-lg font-semibold mb-1">{project.name}</h2>
              <p className="text-sm text-[var(--color-text-muted)]">
                {project.description}
              </p>
            </a>
          ))}
        </div>

        {projects.length === 0 && (
          <p className="text-[var(--color-text-muted)] text-center mt-8">
            No projects found. Add a project to <code>public/graphs/</code> and update <code>index.json</code>.
          </p>
        )}
      </div>
    </div>
  );
}
