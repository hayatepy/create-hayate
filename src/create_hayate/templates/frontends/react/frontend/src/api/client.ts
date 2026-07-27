import createClient from "openapi-fetch";

import type { paths } from "./schema";

export type Todo =
  paths["/api/todos"]["get"]["responses"][200]["content"]["application/json"][number];

const client = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: "include",
});

function requestError(response: Response): Error {
  return new Error(`Hayate request failed ($${response.status} $${response.statusText})`);
}

export async function listTodos(): Promise<Todo[]> {
  const { data, error, response } = await client.GET("/api/todos");
  if (error || !data) {
    throw requestError(response);
  }
  return data;
}

export async function createTodo(title: string): Promise<Todo> {
  const { data, error, response } = await client.POST("/api/todos", {
    body: { title },
  });
  if (error || !data) {
    throw requestError(response);
  }
  return data;
}

export async function updateTodo(id: string, title: string): Promise<Todo> {
  const { data, error, response } = await client.PATCH("/api/todos/{id}", {
    params: { path: { id } },
    body: { title },
  });
  if (error || !data) {
    throw requestError(response);
  }
  return data;
}

export async function deleteTodo(id: string): Promise<void> {
  const { error, response } = await client.DELETE("/api/todos/{id}", {
    params: { path: { id } },
  });
  if (error || !response.ok) {
    throw requestError(response);
  }
}
