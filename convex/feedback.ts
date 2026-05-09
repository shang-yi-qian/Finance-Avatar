import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const saveFeedback = mutation({
  args: {
    userId: v.string(),
    pitchId: v.string(),
    signal: v.union(
      v.literal("too_jargony"),
      v.literal("too_basic"),
      v.literal("nailed_it")
    ),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("feedback", { ...args, createdAt: Date.now() });
  },
});

export const getFeedbackByUser = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    return await ctx.db
      .query("feedback")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .order("desc")
      .take(100);
  },
});
