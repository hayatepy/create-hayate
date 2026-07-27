import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";
import { Link, NavLink, Route, Routes } from "react-router";

import {
  createTodo,
  deleteTodo,
  listTodos,
  type Todo,
  updateTodo,
} from "./api/client";

function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="site-shell">
      <header className="masthead">
        <Link className="wordmark" to="/" aria-label="$project_name home">
          <span className="wordmark-mark" aria-hidden="true">
            H
          </span>
          <span>
            <strong>$project_name</strong>
            <small>Focus desk</small>
          </span>
        </Link>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end>
            Today
          </NavLink>
          <NavLink to="/about">System</NavLink>
        </nav>
      </header>
      {children}
      <footer>
        <span>Hayate owns the contract.</span>
        <span>React owns the interaction.</span>
      </footer>
    </div>
  );
}

function TodoRow({
  todo,
  onDelete,
  onUpdate,
}: {
  todo: Todo;
  onDelete: (id: string) => Promise<void>;
  onUpdate: (id: string, title: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(todo.title);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onUpdate(todo.id, title);
    setEditing(false);
  }

  return (
    <li className="todo-row">
      <span className="todo-index" aria-hidden="true">
        {todo.id.slice(0, 2)}
      </span>
      {editing ? (
        <form className="edit-form" onSubmit={save}>
          <label className="sr-only" htmlFor={`edit-$${todo.id}`}>
            Edit task
          </label>
          <input
            id={`edit-$${todo.id}`}
            value={title}
            maxLength={200}
            required
            onChange={(event) => setTitle(event.target.value)}
          />
          <button className="text-action" type="submit">
            Save
          </button>
          <button
            className="text-action muted"
            type="button"
            onClick={() => {
              setTitle(todo.title);
              setEditing(false);
            }}
          >
            Cancel
          </button>
        </form>
      ) : (
        <>
          <div className="todo-copy">
            <span>{todo.title}</span>
            <small>{todo.done ? "Complete" : "Open"}</small>
          </div>
          <div className="row-actions">
            <button className="text-action" type="button" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button className="text-action danger" type="button" onClick={() => onDelete(todo.id)}>
              Delete
            </button>
          </div>
        </>
      )}
    </li>
  );
}

function FocusDesk() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("Loading your focus list…");

  const refresh = useCallback(async () => {
    const next = await listTodos();
    setTodos(next);
    setMessage(
      next.length
        ? `$${next.length} open signal$${next.length === 1 ? "" : "s"}`
        : "Clear desk",
    );
  }, []);

  useEffect(() => {
    let active = true;
    listTodos()
      .then((next) => {
        if (active) {
          setTodos(next);
          setMessage(
            next.length
              ? `$${next.length} open signal$${next.length === 1 ? "" : "s"}`
              : "Clear desk",
          );
        }
      })
      .catch(() => active && setMessage("Hayate is unavailable"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) return;
    setMessage("Adding signal…");
    try {
      await createTodo(nextTitle);
      setTitle("");
      await refresh();
    } catch {
      setMessage("Could not add that signal");
    }
  }

  async function update(id: string, nextTitle: string) {
    setMessage("Saving…");
    try {
      await updateTodo(id, nextTitle.trim());
      await refresh();
    } catch {
      setMessage("Could not save that signal");
    }
  }

  async function remove(id: string) {
    setMessage("Clearing…");
    try {
      await deleteTodo(id);
      await refresh();
    } catch {
      setMessage("Could not clear that signal");
    }
  }

  return (
    <main>
      <section className="hero" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">One deliberate queue</p>
          <h1 id="page-title">
            Decide what
            <br />
            moves <em>today.</em>
          </h1>
        </div>
        <div className="hero-note">
          <span className="pulse" aria-hidden="true" />
          <p aria-live="polite">{loading ? "Loading your focus list…" : message}</p>
          <small>Typed from Hayate OpenAPI</small>
        </div>
      </section>

      <section className="workbench" aria-label="Task workspace">
        <form className="capture" onSubmit={add} aria-busy={loading}>
          <label htmlFor="new-task">New signal</label>
          <div className="capture-line">
            <input
              id="new-task"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="What deserves attention?"
              maxLength={200}
              required
              autoComplete="off"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !title.trim()}>
              Add to desk
            </button>
          </div>
        </form>

        <div className="list-heading">
          <h2>Working set</h2>
          <span>{String(todos.length).padStart(2, "0")}</span>
        </div>
        {todos.length ? (
          <ul className="todo-list">
            {todos.map((todo) => (
              <TodoRow key={todo.id} todo={todo} onDelete={remove} onUpdate={update} />
            ))}
          </ul>
        ) : (
          <div className="empty-state">
            <span aria-hidden="true">○</span>
            <p>The desk is open. Add one concrete next move.</p>
          </div>
        )}
      </section>
    </main>
  );
}

function About() {
  return (
    <main className="system-page">
      <p className="eyebrow">Architecture note</p>
      <h1>Two layers.<br />One contract.</h1>
      <div className="system-grid">
        <section>
          <span>01</span>
          <h2>Hayate</h2>
          <p>Owns identity, validation, storage, and every endpoint below `/api`.</p>
        </section>
        <section>
          <span>02</span>
          <h2>OpenAPI</h2>
          <p>Projects the route contract into checked, generated TypeScript.</p>
        </section>
        <section>
          <span>03</span>
          <h2>React</h2>
          <p>Owns browser state and interaction without becoming another backend.</p>
        </section>
      </div>
      <Link className="return-link" to="/">Return to the desk →</Link>
    </main>
  );
}

function NotFound() {
  return (
    <main className="not-found">
      <p className="eyebrow">404</p>
      <h1>That signal is off the map.</h1>
      <Link className="return-link" to="/">Return home →</Link>
    </main>
  );
}

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<FocusDesk />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Shell>
  );
}
