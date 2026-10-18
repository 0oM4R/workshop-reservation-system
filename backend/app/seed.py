"""Insert the demo workshops; safe to rerun.

Run with `python -m app.seed`.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.models import Workshop
from app.settings import settings


class DemoWorkshop(NamedTuple):
    """Demo workshop starting `days` from today at 10:00 UTC."""

    slug: str
    title: str
    days: int
    capacity: int
    description: str


# Varied topics, levels and formats give search something to rank.
# Knife Skills has one seat, so one reservation shows a full workshop.
DEMO_WORKSHOPS = [
    DemoWorkshop(
        "intro-to-pottery",
        "Intro to Pottery",
        3,
        8,
        "A beginner studio session at the potter's wheel. Learn to center clay, "
        "throw a simple bowl and trim it, then glaze a piece to take home after "
        "firing. No experience needed; aprons provided.",
    ),
    DemoWorkshop(
        "watercolor-basics",
        "Watercolor Basics",
        5,
        12,
        "A relaxed beginner class in painting with watercolors. Practice washes, "
        "color mixing and layering while you paint a small landscape step by "
        "step. All materials are included.",
    ),
    DemoWorkshop(
        "sourdough-baking",
        "Sourdough Baking",
        7,
        10,
        "A hands-on kitchen workshop for home bakers. Feed a starter, mix and fold "
        "a dough, shape a loaf and bake it in a Dutch oven. You leave with your "
        "own starter and a fresh loaf of bread.",
    ),
    DemoWorkshop(
        "bike-repair-101",
        "Bike Repair 101",
        10,
        6,
        "Beginner mechanics for everyday cyclists, working on your own bicycle. "
        "Fix a flat tire, adjust brakes and gears, and clean and oil the chain. "
        "Bring your bike; tools are provided.",
    ),
    DemoWorkshop(
        "knife-skills",
        "Knife Skills",
        14,
        1,
        "A private one-to-one lesson with a chef. Learn to hold, sharpen and care "
        "for a kitchen knife, then dice, julienne and chiffonade vegetables "
        "safely and quickly. Suits beginners and keen home cooks.",
    ),
    DemoWorkshop(
        "photography-walk",
        "Photography Walk",
        21,
        15,
        "An outdoor walk through the old town for photographers of every level. "
        "Practice composition, light and street photography with whatever camera "
        "you have, phones included, and review your shots together over coffee.",
    ),
    DemoWorkshop(
        "spreadsheet-data-cleaning",
        "Cleaning Data in Spreadsheets",
        4,
        20,
        "A beginner, hands-on lab for anyone who works with messy spreadsheets. "
        "Remove duplicates, fix dates and text, and summarize a real dataset with "
        "formulas and pivot tables. No programming required.",
    ),
    DemoWorkshop(
        "sql-from-scratch",
        "SQL from Scratch",
        6,
        16,
        "A beginner course in querying relational databases, taught over three "
        "evening sessions. Write SELECT statements, filter and sort rows, join "
        "tables and aggregate results, with exercises on a sample shop database.",
    ),
    DemoWorkshop(
        "python-data-analysis",
        "Data Analysis with Python",
        9,
        14,
        "An intermediate hands-on lab in Jupyter notebooks. Load, reshape and "
        "explore datasets with pandas, then answer business questions with "
        "group-bys and charts. Assumes basic Python.",
    ),
    DemoWorkshop(
        "data-storytelling",
        "Telling Stories with Charts",
        12,
        25,
        "A talk with short exercises on data visualization, for all levels. "
        "Choose the right chart, strip out clutter and build a dashboard that "
        "makes one clear point to your audience.",
    ),
    DemoWorkshop(
        "machine-learning-fundamentals",
        "Machine Learning Fundamentals",
        16,
        30,
        "An intermediate lecture with live coding demos. Covers regression, "
        "classification, overfitting and how to evaluate a model honestly, using "
        "scikit-learn on small, real examples.",
    ),
    DemoWorkshop(
        "llm-applications",
        "Building Apps on Large Language Models",
        23,
        12,
        "An advanced, hands-on lab for developers. Design prompts, add retrieval "
        "over your own documents, call tools, and measure answer quality with a "
        "small evaluation set.",
    ),
    DemoWorkshop(
        "threat-modeling",
        "Threat Modeling Basics",
        8,
        18,
        "An interactive beginner session for product teams. Map how attackers "
        "could abuse a system, rank the risks and decide which defenses matter "
        "most, working in small groups on a sample web application.",
    ),
    DemoWorkshop(
        "secure-coding",
        "Secure Coding for Web Developers",
        19,
        14,
        "An advanced, hands-on lab. Find and fix injection, cross-site scripting "
        "and broken authentication in a deliberately vulnerable web application, "
        "and add checks that keep them from coming back.",
    ),
    DemoWorkshop(
        "continuous-delivery",
        "Continuous Delivery Pipelines",
        11,
        16,
        "An intermediate, hands-on workshop on CI/CD. Build a pipeline that "
        "tests, packages and deploys every commit automatically, so releases "
        "become small, frequent and boring.",
    ),
    DemoWorkshop(
        "agile-delivery",
        "Agile Delivery for Product Teams",
        13,
        24,
        "A practical session for whole teams at any level. Plan in short "
        "iterations, limit work in progress, run useful retrospectives and cut "
        "the wait between an idea and a release.",
    ),
    DemoWorkshop(
        "containers-kubernetes",
        "Containers and Kubernetes in Practice",
        26,
        12,
        "An advanced, hands-on lab. Package a service with Docker, deploy it to a "
        "Kubernetes cluster, then scale it, roll out a new version and roll it "
        "back.",
    ),
    DemoWorkshop(
        "git-for-teams",
        "Git for Teams",
        5,
        20,
        "A beginner, hands-on workshop on version control. Create branches, open "
        "pull requests, review code and resolve merge conflicts in a shared "
        "practice repository.",
    ),
    DemoWorkshop(
        "test-driven-development",
        "Test-Driven Development Dojo",
        17,
        10,
        "An intermediate coding dojo held in pairs. Write a failing test first, "
        "make it pass and refactor, practicing on small katas until the rhythm "
        "feels natural.",
    ),
    DemoWorkshop(
        "user-research",
        "User Interviews and Usability Testing",
        15,
        16,
        "A beginner, hands-on workshop in user research. Plan interviews, run a "
        "usability test with a real participant and turn your notes into findings "
        "the team can act on.",
    ),
    DemoWorkshop(
        "figma-interface-design",
        "Interface Design in Figma",
        20,
        18,
        "A beginner, hands-on class for aspiring designers. Lay out screens with "
        "auto layout, build reusable components and link them into a clickable "
        "prototype.",
    ),
    DemoWorkshop(
        "web-accessibility",
        "Web Accessibility Essentials",
        27,
        20,
        "An intermediate workshop for designers and developers. Test pages with a "
        "screen reader and keyboard only, fix color contrast and labels, and "
        "learn the WCAG guidelines that matter most.",
    ),
    DemoWorkshop(
        "product-roadmaps",
        "Product Roadmaps and Prioritization",
        30,
        20,
        "An intermediate, discussion-based workshop for product managers. Turn "
        "goals into outcomes, compare prioritization methods and present a "
        "roadmap stakeholders can trust.",
    ),
    DemoWorkshop(
        "public-speaking",
        "Confident Public Speaking",
        9,
        12,
        "A practice-heavy class for all levels. Structure a short talk, calm your "
        "nerves, use your voice and pauses, and deliver a three-minute talk with "
        "friendly feedback from the group.",
    ),
    DemoWorkshop(
        "first-time-managers",
        "Leading Your First Team",
        18,
        15,
        "A discussion-based program for new managers, over four weekly sessions. "
        "Hold good one-on-ones, delegate clearly, set expectations and handle "
        "difficult conversations.",
    ),
    DemoWorkshop(
        "feedback-conversations",
        "Giving and Receiving Feedback",
        22,
        16,
        "An all-levels workshop built on role-play. Practice giving specific, "
        "kind feedback, receiving criticism without getting defensive and turning "
        "it into next steps.",
    ),
    DemoWorkshop(
        "remote-meetings",
        "Running Effective Remote Meetings",
        24,
        40,
        "A live online session over video call. Write agendas that lead to "
        "decisions, facilitate so everyone speaks, and replace status meetings "
        "with written async updates.",
    ),
    DemoWorkshop(
        "personal-finance",
        "Personal Finance Basics",
        12,
        40,
        "An evening talk for beginners about money. Build a budget, set up an "
        "emergency fund, pay down debt and understand index funds and retirement "
        "accounts, with time for questions.",
    ),
    DemoWorkshop(
        "short-story-writing",
        "Short Story Writing",
        25,
        10,
        "A beginner writing circle. Short prompts help you build characters, "
        "dialogue and a scene, and you share drafts for gentle feedback from the "
        "group.",
    ),
    DemoWorkshop(
        "desk-yoga",
        "Yoga for Desk Workers",
        2,
        20,
        "A gentle class for all levels. Stretches and posture exercises that ease "
        "neck and back pain from long days sitting at a computer, all doable in "
        "office clothes.",
    ),
    DemoWorkshop(
        "mindfulness-stress",
        "Mindfulness and Stress Management",
        28,
        25,
        "A beginner course in guided practice, held online over four weeks. Learn "
        "breathing and attention exercises, spot early signs of burnout and build "
        "a short daily routine.",
    ),
    DemoWorkshop(
        "balcony-gardening",
        "Balcony Gardening",
        33,
        15,
        "A beginner, hands-on session on growing food in small spaces. Choose "
        "containers and soil, plant herbs and vegetables, and keep them watered "
        "and healthy on a balcony or windowsill.",
    ),
    DemoWorkshop(
        "arduino-electronics",
        "Electronics with Arduino",
        35,
        12,
        "A beginner, hands-on build. Wire circuits on a breadboard, read sensors, "
        "blink LEDs and program a microcontroller to make a small gadget you take "
        "home.",
    ),
    DemoWorkshop(
        "fresh-pasta",
        "Fresh Pasta by Hand",
        31,
        10,
        "A hands-on cooking class for beginners. Make egg pasta dough, roll it by "
        "hand, cut tagliatelle and fill ravioli, then cook and eat them with two "
        "simple sauces.",
    ),
    DemoWorkshop(
        "spanish-for-travelers",
        "Spanish for Travelers",
        38,
        14,
        "A beginner conversation class. Practice the phrases you need for "
        "ordering food, asking directions and checking in, through role-play with "
        "a native speaker.",
    ),
    DemoWorkshop(
        "incident-response",
        "Monitoring and Incident Response",
        40,
        16,
        "An advanced workshop for engineers on call. Set up useful alerts from "
        "logs, metrics and traces, run a simulated outage end to end and write a "
        "blameless postmortem.",
    ),
]


async def seed(connection: AsyncConnection) -> int:
    """Insert missing demo workshops and update existing descriptions.

    Existing rows keep their date, capacity and seat count.

    Returns:
        Rows inserted or updated.
    """
    # Relative to today, so a fresh database always shows upcoming workshops.
    ten_am_today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    rows = [
        {
            "slug": workshop.slug,
            "title": workshop.title,
            "description": workshop.description,
            "starts_at": ten_am_today + timedelta(days=workshop.days),
            "capacity": workshop.capacity,
        }
        for workshop in DEMO_WORKSHOPS
    ]
    statement = insert(Workshop).values(rows)
    result = await connection.execute(
        statement.on_conflict_do_update(
            index_elements=["slug"],
            set_={"description": statement.excluded.description},
            # Skips unchanged rows, so a rerun writes nothing.
            where=Workshop.description.is_distinct_from(statement.excluded.description),
        )
    )
    return result.rowcount


async def main() -> None:
    """Seed the application database."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        written = await seed(connection)
    await engine.dispose()
    print(f"Inserted or updated {written} demo workshops.")


if __name__ == "__main__":
    asyncio.run(main())
