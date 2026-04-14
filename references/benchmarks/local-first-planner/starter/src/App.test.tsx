import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the benchmark starter heading", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Local First Planner" })).toBeInTheDocument();
  });
});
