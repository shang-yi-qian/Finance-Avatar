import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getUser = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    return await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .first();
  },
});

export const upsertUser = mutation({
  args: {
    userId: v.string(),
    displayName: v.string(),
    avatarImageUrl: v.string(),
    voiceId: v.string(),
    portfolio: v.array(
      v.object({ ticker: v.string(), weight: v.number(), avgCost: v.number() })
    ),
    styleProfileSummary: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", args.userId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { ...args });
      return existing._id;
    }
    return await ctx.db.insert("users", { ...args, createdAt: Date.now() });
  },
});

export const updateStyleSummary = mutation({
  args: { userId: v.string(), styleProfileSummary: v.string() },
  handler: async (ctx, { userId, styleProfileSummary }) => {
    const user = await ctx.db
      .query("users")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .first();
    if (user) {
      await ctx.db.patch(user._id, { styleProfileSummary });
    }
  },
});

