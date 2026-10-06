import { describe, expect, it } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { invalidateWorkspaceLeads, leadKeys } from "./leadQueries";

describe("lead query keys", () => {
  it("nests dashboard, pipeline, and list keys under [leads, workspaceId]", () => {
    const workspaceId = "ws-1";
    const prefix = leadKeys.all(workspaceId);

    expect(leadKeys.total(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.count(workspaceId, "NEW").slice(0, 2)).toEqual(prefix);
    expect(leadKeys.recent(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.pipeline(workspaceId, "WON").slice(0, 2)).toEqual(prefix);
    expect(leadKeys.lookup(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.list(workspaceId, { page: 1 }).slice(0, 2)).toEqual(prefix);
  });

  it("invalidates inactive dashboard total/count/recent queries", () => {
    const queryClient = new QueryClient();
    const workspaceId = "ws-1";
    queryClient.setQueryData(leadKeys.total(workspaceId), { items: [], total: 3 });
    queryClient.setQueryData(leadKeys.count(workspaceId, "NEW"), { items: [], total: 2 });
    queryClient.setQueryData(leadKeys.recent(workspaceId), { items: [], total: 3 });

    invalidateWorkspaceLeads(queryClient, workspaceId);

    expect(queryClient.getQueryState(leadKeys.total(workspaceId))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(leadKeys.count(workspaceId, "NEW"))?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(leadKeys.recent(workspaceId))?.isInvalidated).toBe(true);
  });
});

describe("lead query keys", () => {
  it("nests dashboard, pipeline, and list keys under [leads, workspaceId]", () => {
    const workspaceId = "ws-1";
    const prefix = leadKeys.all(workspaceId);

    expect(leadKeys.total(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.count(workspaceId, "NEW").slice(0, 2)).toEqual(prefix);
    expect(leadKeys.recent(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.pipeline(workspaceId, "WON").slice(0, 2)).toEqual(prefix);
    expect(leadKeys.lookup(workspaceId).slice(0, 2)).toEqual(prefix);
    expect(leadKeys.list(workspaceId, { page: 1 }).slice(0, 2)).toEqual(prefix);
  });
});
