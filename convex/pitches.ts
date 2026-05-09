import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const savePitch = mutation({
  args: {
    userId: v.string(),
    ticker: v.string(),
    fitScore: v.number(),
    breakdown: v.any(),
    spokenText: v.string(),
    audioUrl: v.optional(v.string()),
    videoUrl: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("pitches", { ...args, createdAt: Date.now() });
  },
});

export const getPitchesByUser = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    return await ctx.db
      .query("pitches")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .order("desc")
      .take(50);
  },
});

export const getLatestPitch = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    return await ctx.db
      .query("pitches")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .order("desc")
      .first();
  },
});
