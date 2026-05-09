import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  users: defineTable({
    userId: v.string(),
    displayName: v.string(),
    avatarImageUrl: v.string(),
    voiceId: v.string(),
    portfolio: v.array(
      v.object({
        ticker: v.string(),
        weight: v.number(),
        avgCost: v.number(),
      })
    ),
    styleProfileSummary: v.string(),
    createdAt: v.number(),
  }).index("by_userId", ["userId"]),

  pitches: defineTable({
    userId: v.string(),
    ticker: v.string(),
    fitScore: v.number(),
    breakdown: v.any(),
    spokenText: v.string(),
    audioUrl: v.optional(v.string()),
    videoUrl: v.optional(v.string()),
    createdAt: v.number(),
  }).index("by_userId", ["userId"]),

  feedback: defineTable({
    userId: v.string(),
    pitchId: v.string(),
    signal: v.union(
      v.literal("too_jargony"),
      v.literal("too_basic"),
      v.literal("nailed_it")
    ),
    createdAt: v.number(),
  }).index("by_userId", ["userId"]),
});

