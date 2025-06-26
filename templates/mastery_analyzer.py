import json

def calculate_mastery_level(records):
    knowledge_stats = {}
    for record in records:
        kp = record.get('knowledge_point')
        if not kp:
            continue
        if kp not in knowledge_stats:
            knowledge_stats[kp] = {"total": 0, "correct": 0}
        knowledge_stats[kp]["total"] += 1
        if record.get('is_correct'):
            knowledge_stats[kp]["correct"] += 1

    mastery = {}
    for kp, stats in knowledge_stats.items():
        rate = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        mastery[kp] = round(rate * 100, 2)
    return mastery