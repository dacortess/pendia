import "@testing-library/jest-dom";
import { beforeAll, afterEach, afterAll } from "vitest";
import { server } from "./server";
import { configureAuth } from "@/lib/api-client";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  configureAuth({
    getToken: () => null,
    setToken: () => {},
    onRefreshFailed: () => {},
  });
});
afterAll(() => server.close());
