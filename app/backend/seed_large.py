"""DEMO: PHIL 101, a big lecture course, to show Dialectic with a crowded margin.

seed.py --reset adds it every time. It's week 2: Locke (last week, a rough scan) is heavily
annotated, Rousseau (this week) is crowded and densest on the general-will sentence on p. 12,
and Mill (next week, a very rough 1859 xerox) has three notes. Log in as Maya: she has written
nothing anywhere, so every margin is lock cards ("N notes near here"); add a note on the
general-will sentence and they open. Jordan writes a lot, so his margins are mostly open.
"""
from pathlib import Path

import db
from seed_notes import Rota, add_charter_comments, add_notes, add_reading, days_ago

SEED_DIR = Path(__file__).parent / "seed"
COURSE_TITLE = "PHIL 101: Introduction to Political Philosophy (lecture)"
CURRENT_COHORT = "Fall 2026"
PAST_COHORT = "Spring 2026"
PROFESSOR = "Prof. Okafor"

# Maya and Jordan are the ones to log in as, and come first in the log-in list.
FEATURED_STUDENTS = ["Maya", "Jordan"]

# The other current students. Names are only labels; they write the "None" notes below in turn.
CLASSMATES = """
Aaliyah Abdul Adrian Aiden Amara Andre Ari Asha Ava Bea Caleb Camila Chloe Daniel Darius Destiny
Diego Elena Eli Emeka Esme Ethan Fatima Gabe Grace Hana Imani Isaac Jada Jalen Jasmine Kai Kemi Kenji
Lena Liam Lucia Malik Marcus Mateo Mei Naomi Nia Noah Olivia Omar Priya Quinn Rafael Riya Rosa Ruth
Sana Simone Talia Theo Tomas Uma Victor Wren Yusuf Zara Zoe
""".split()

# Last year's lecture: their notes show with a "Spring 2026" badge.
PAST_STUDENTS = ["Devon", "Harper", "Ines", "Jonah", "Kiara", "Luca", "Mira", "Nadia"]

# Rule 4 is the big-class rule. Rule 6 and the IEP in the sources came from student proposals.
CHARTER_TEXT = """1. Read the text first, then ask the class. AI comes last.
2. AI may find sources and give historical background. It may not tell us what the text means or write our response papers.
3. Anything AI writes is public to the class and labelled as AI.
4. There are a lot of us: reply to a thread on a passage before starting a new one on the same line.
5. Annotations are shared with future classes unless you untick the box.
6. If a scan is too rough to select, use Select area and type the words you mean; don't guess from another edition."""

PERMISSIBLE_SOURCES = (
    "Scholarly encyclopedias (Stanford Encyclopedia of Philosophy, Internet Encyclopedia of Philosophy, "
    "Britannica), peer-reviewed scholarship, university and museum sites, and primary texts from "
    "1600–1870. No study-guide or essay-mill sites. Wikipedia only for dates and names."
)
MAX_EXPLANATION_WORDS = 100

# DEMO: charter proposals in every state. (who, body, status)
CHARTER_COMMENTS = [
    ("Jordan", "Propose allowing the Internet Encyclopedia of Philosophy (iep.utm.edu). It's peer-reviewed "
               "and easier going than SEP for an intro class.", "added"),
    ("Kai", "Could the AI write a one-paragraph summary of each reading before lecture, for people who "
            "fall behind?", "declined"),
    ("Imani", "The Locke scan is really hard to select on some pages. Can we have a rule for what to do "
              "when the text won't highlight?", "added"),
    ("Theo", "Propose allowing recorded university lectures (Yale Open Courses etc.) as sources.", "open"),
    ("Rosa", "Rule 4 is good but there are already six threads on 'Man is born free'. Can the TA merge them?", "open"),
]

# ---------- Week 1: Locke, Second Treatise ch. I–III. A rough Digital Library of India scan.
# Quotes are as the scan's OCR reads them (e.g. p. 11 really does say "Tue natural liberty ... an superior power").
LOCKE_PDF = SEED_DIR / "locke-second-treatise-ch1-3.pdf"
LOCKE_TITLE = "Week 1 · Locke, Second Treatise of Government, ch. I–III"
LOCKE_NOTES = [
    # ---- p. 1–2: what political power is
    (1, "Adam’s private dominion and paternal jurisdiction", "note", PROFESSOR,
     "The First Treatise (not assigned) is a long attack on Filmer, who said kings inherit Adam's authority. "
     "This paragraph is the summary: that theory is dead, so where does power come from?", []),
    (1, "the product only of force and violence", "note", None,
     "Locke's worry is the same as Rousseau's next week: is government just force with better branding?", []),
    (2, "Political power, then, I take to be a right of making laws, with penalties of death", "note", None,
     "Definition first. Notice 'only for the public good' at the end of the paragraph.", [
         (None, "And 'regulating and preserving of property' is in there from the start."),
         (PROFESSOR, "Keep that in mind: 'property' for Locke will turn out to include life and liberty."),
     ]),
    (2, "a father of a iamily, and a, captain of a galley", "note", "Jordan",
     "The OCR reads 'family' as 'iamily' here, ha. The point: political power is different from every "
     "other kind of power over people.", []),
    # ---- p. 2–4: the state of nature
    (2, "a state of perfect freedom to order their actions", "note", None,
     "Compare Hobbes: Locke's state of nature starts as freedom, not war.", [
         ("Jordan", "But 'within the bounds of the law of Nature': it's freedom with rules already in it."),
     ]),
    (2, "a state of perfect freedom to order their actions", "note", "past",
     "Our TA said to read 'perfect' as 'complete', not 'ideal'.", []),
    (2, "without asking leave or depending upon the will of any other man", "note", None,
     "Freedom = not depending on someone else's will. That definition comes back in Rousseau.", []),
    (2, "A state also of equality", "note", None, "Freedom and equality, in that order.", []),
    (3, "the judicious Hooker", "question", None, "Who is Hooker and why does Locke keep quoting him?", [
         (None, "Richard Hooker, Elizabethan theologian. Quoting him makes Locke sound safely Anglican."),
     ]),
    (3, "But though this be a state of liberty, yet it is not a state of licence", "note", None,
     "Liberty vs licence is the key distinction of the chapter.", [
         (None, "Licence = doing whatever you want. Liberty = freedom within the law of nature."),
         (None, "So you can't even destroy yourself. That's a big limit."),
     ]),
    (3, "But though this be a state of liberty, yet it is not a state of licence", "note", "Jordan",
     "Writing my response paper on this line.", []),
    (3, "The state of Nature has a law of Nature to govern it", "note", "past",
     "The difference from Hobbes in one sentence.", []),
    (3, "no one ought to harm another in his life, health, liberty or possessions", "note", None,
     "Life, health, liberty, possessions. Jefferson's list is a remix.", [
         (None, "'Pursuit of happiness' replaced property. People still argue about why."),
     ]),
    (3, "all the workmanship of one omnipotent and infinitely wise Maker", "note", None,
     "The argument depends on God. Would it work without him?", []),
    (4, "they are His property, whose workmanship, they are made to last during His, not one another’s pleasure",
     "note", PROFESSOR, "We are God's property, which is why we can't sell ourselves into slavery (ch. IV).", []),
    (4, "the execution of the law of Nature is in that state put into every man’s hands", "note", None,
     "Everyone is a police officer and judge. That's the problem the rest of the book solves.", []),
    (4, "every one has a right to punish the transgressors of that law", "question", None,
     "If everyone can punish, what stops revenge?", [
         ("Jordan", "Next paragraph: only 'as calm reason and conscience dictate'. Proportionate punishment."),
         (None, "Which is exactly what people are bad at. He admits it on p. 7."),
     ]),
    (4, "so far as calm reason and conscience dictate", "note", None, "Easier said than done.", []),
    # ---- p. 5–6: strange doctrine, punishing aliens
    (5, "I doubt not but this will seem a very strange doctrine to some men", "note", None,
     "He knows the executive power of nature sounds weird, so he gives an argument from foreigners.", []),
    (5, "to an Indian, but like the rest of the world—men without authority", "note", PROFESSOR,
     "The argument: a state can punish a foreigner even though its laws don't bind him, so the right to "
     "punish must come from nature. Watch how often 'Indians' and America show up as examples.", []),
    (6, "may be destroyed as a lion or a tiger", "note", None,
     "A murderer has declared war on all mankind. Very harsh.", []),
    (6, "Every one that findeth me shall slay me", "note", None, "Genesis 4. Cain after killing Abel.", []),
    # ---- p. 7–8: judges in their own case, where is the state of nature
    (7, "self-love will make men partial to themselves and their friends", "note", None,
     "The best objection to Locke, and he states it himself.", []),
    (7, "absolute monarchs are but men", "note", None,
     "Great comeback: if being judge in your own case is bad, an absolute king is the worst case of it.", [
         (None, "This is a shot at Hobbes's sovereign."),
         (PROFESSOR, "Yes. Hold on to it for the week on Leviathan's sovereign."),
     ]),
    (7, "absolute monarchs are but men", "note", "past", "My favourite line in the Second Treatise.", []),
    (8, "where are, or ever were, there any men in such a state of Nature?", "note", None,
     "The 'when did this ever happen?' objection.", []),
    (8, "all princes and rulers of “independent” governments", "note", None,
     "His answer: countries are in a state of nature with each other right now. Same move as Hobbes.", []),
    (8, "between a Swiss and an Indian, in the woods of America", "note", None,
     "Promises bind even without government. Keeping faith belongs to men as men.", []),
    (8, "keeping of faith belongs to men as men, and not as members of society", "note", "Jordan",
     "This is why Locke's contract can work: promising is already possible before the state.", []),
    # ---- p. 9–12: the state of war, slavery
    (9, "THE state of war is a state of enmity and destruction", "note", PROFESSOR,
     "Chapter III separates the state of war from the state of nature, which Hobbes had run together.", []),
    (9, "he may kill a wolf or a lion", "note", None, "Animal comparisons again (see p. 6).", []),
    (9, "he who attempts to get another man into his absolute power does thereby put himself into a state of war with him",
     "note", None, "Trying to enslave someone = declaring war on them. Big for later arguments about revolution.", []),
    (10, "This makes it lawful for a man to kill a thief", "note", None,
     "Wild example, but the logic is: you can't know what someone who uses force on you will stop at.", [
         (None, "Self-defence law still uses a version of this."),
     ]),
    (10, "the plain difference between the state of Nature and the state of war", "note", "Jordan",
     "Nature = no common judge. War = force without right. You can have war even inside society.", []),
    (10, "Men living together according to reason without a common superior on earth", "note", None,
     "Cleanest definition of the state of nature in the text.", []),
    (11, "Where there is no judge on earth the appeal lies to God in Heaven.", "note", None,
     "'Appeal to Heaven' became a slogan on American revolutionary flags.", []),
    (11, "natural liberty of man is to be free from an superior power on earth", "note", "Jordan",
     "The scan's text says 'Tue natural liberty' and 'an superior'; the book says 'The' and 'any'. "
     "Chapter IV, on slavery, starts here.", []),
    (12, "cannot by compact or his own consent enslave himself to any one", "note", None,
     "You can't sell what you don't own, and you don't own your own life.", []),
    (12, "the state of war continued between a lawful conqueror and a captive", "note", PROFESSOR,
     "Slavery as war continued. Rousseau says almost the same thing in Book 1 ch. 4, so read them side by side.", []),
]

# ---------- Week 2: Rousseau, The Social Contract (Bennett). Crowded; densest on p. 12.
ROUSSEAU_PDF = SEED_DIR / "rousseau-social-contract.pdf"
ROUSSEAU_TITLE = "Week 2 · Rousseau, The Social Contract"
ROUSSEAU_NOTES = [
    # ---- p. 6: the opening
    (6, "With men as they are and with laws as they could be", "note", PROFESSOR,
     "The method in one phrase: take people as they are, imagine the laws as they could be.", []),
    (6, "I answer that I am neither, and that is why I write on politics.", "note", None,
     "Sassy. If he were a prince he'd act instead of writing.", []),
    (6, "As I was born a citizen of a free state", "note", None,
     "Geneva. He signs his books 'citizen of Geneva'.", [
         (None, "And Geneva later burned this book, I think?"),
         (PROFESSOR, "Yes, in 1762, along with Emile."),
     ]),
    (6, "Man is born free, and everywhere he is in chains.", "note", None,
     "The most famous line, and he immediately says he doesn't know how it happened.", []),
    (6, "Man is born free, and everywhere he is in chains.", "note", None,
     "Born free = natural liberty. Chains = society as it exists. He's not against society, he's asking "
     "what would make the chains legitimate.", [
         (None, "Wait, so legitimate chains are OK?"),
         (None, "I think 'chains' becomes 'laws you gave yourself' by Book 1 ch. 8."),
         ("Jordan", "Yes, p. 15: 'obedience to a law that we prescribe to ourselves is liberty'."),
     ]),
    (6, "Man is born free, and everywhere he is in chains.", "note", "past",
     "Last spring half the class wrote their first paper on this sentence.", []),
    (6, "Man is born free, and everywhere he is in chains.", "question", None,
     "Is this an answer to Hobbes or to Locke?", [
         (None, "Both? Hobbes says no freedom in nature, Locke says freedom ends with property."),
     ]),
    (6, "Man is born free, and everywhere he is in chains.", "note", "Jordan",
     "Notice 'he thinks he is the master of others, yet he is more enslaved'. The masters are in chains too.", []),
    (6, "How did this change come about? I don’t know.", "note", None,
     "Funny since he wrote a whole Discourse on exactly this (the Second Discourse, 1755).", []),
    (6, "What can make it legitimate? That’s a question that I think I can answer.", "note", None,
     "Legitimacy, not history. That's the whole book's question.", []),
    (6, "is a sacred right on which all other rights are based", "note", None,
     "The social order is a right but not natural, so it has to be agreed on.", []),
    (6, "The most ancient of all societies, and the only natural one, is the society of the family.", "note", None,
     "Even the family stops being natural once the kids grow up. After that it's by agreement.", []),
    # ---- p. 7–8: against Grotius, force, the right of the strongest
    (7, "the ruler’s care for the people under him is repaid not by love for them", "note", None,
     "The father analogy breaks: fathers love their kids, rulers love being in charge.", []),
    (7, "His usual method of reasoning is to establish right by fact", "note", PROFESSOR,
     "The is/ought point. Grotius describes what happens and calls it right.", [
         (None, "Hume makes this famous a few years earlier, right?"),
         (PROFESSOR, "Treatise of Human Nature, 1739. Good connection."),
     ]),
    (7, "either kings were gods or men were beasts", "note", None, "Caligula's logic, with a straight face.", []),
    (7, "Force made the first slaves, and their cowardice kept them as slaves.", "note", None,
     "Harsh. Is he blaming slaves?", [
         (None, "I read it as: once you're born into it you can lose even the wish to escape. That's the horror."),
         (None, "Compare Aristotle's natural slaves, which he's flipping here."),
     ]),
    (7, "as Robinson Crusoe was of his island", "note", None, "Sovereign of nobody. He's mocking Filmer's Adam.", []),
    (8, "Force is a physical power; I don’t see what moral effect it can have.", "note", None,
     "Might doesn't make right, argued in one line.", []),
    (8, "what sort of right is it that perishes when force fails?", "note", "Jordan",
     "If 'right' just means 'strongest', the word adds nothing.", []),
    (8, "A robber confronts me at the edge of a wood", "note", None,
     "Same thief as Locke ch. III! Locke says I may kill him; Rousseau says I'm not obliged to obey him.", [
         (None, "Good catch. The robber is a classic example."),
     ]),
    (8, "After all, the pistol he holds is also a power.", "note", None, "Great line. 'All power comes from God' -> so does the pistol.", []),
    (8, "You can live peacefully in a dungeon, but does that make it a good life?", "note", None,
     "Against Hobbes: peace isn't enough if the peace is a prison.", []),
    (8, "The Greeks imprisoned in the cave of the Cyclops", "question", None, "What's this referring to?", [
         (None, "The Odyssey, the Cyclops eats Odysseus's men one by one."),
     ]),
    # ---- p. 9–10: slavery, war
    (9, "the man who does it is out of his mind", "note", None, "Giving yourself away for nothing is madness, so not a contract.", []),
    (9, "to remove all freedom from his will is to remove all morality from his actions", "note", None,
     "Freedom is a condition of morality. Kant reads this.", [
         (PROFESSOR, "He did, closely. There's a story that Kant missed his daily walk reading Emile."),
     ]),
    (9, "to remove all freedom from his will is to remove all morality from his actions", "note", "past",
     "This is the sentence that connects the political argument to ethics.", []),
    (9, "Men are not naturally one anothers’ enemies.", "note", None, "Direct hit on Hobbes ch. 13.", []),
    (9, "War is constituted by a relation between things, not between persons", "note", None,
     "So only states make war. Individuals in nature can't have a 'state of war'. Different from Locke too.", []),
    (10, "The words ‘slave’ and ‘right’ contradict each other", "note", "Jordan",
     "Conclusion of ch. 4. Locke got here too, but by a different route (God owns us).", []),
    # ---- p. 11: the social compact
    (11, "Ruling a society will always be a quite different thing from subduing a multitude.", "note", None,
     "Cluster vs association.", []),
    (11, "like an oak that falls into a fire", "note", None, "An empire built on force is just ash when the ruler dies.", []),
    (11, "A hundred men want to have a master; what gives them the right to vote on behalf of ten who don’t?",
     "note", None, "Why majority rule needs a first unanimous agreement. Really clever.", [
         (None, "So unanimity is needed exactly once."),
     ]),
    (11, "still obeys only himself and remains as free as before", "note", PROFESSOR,
     "THE problem of the book. Unite with everyone, obey only yourself. Read it twice.", []),
    (11, "still obeys only himself and remains as free as before", "note", None,
     "How can you obey the group and only yourself at the same time? That seems impossible.", [
         (None, "Only if the group's will is somehow your own will. Which is the general will."),
         ("Jordan", "Right, that's why the next page introduces it."),
     ]),
    (11, "still obeys only himself and remains as free as before", "note", "past", "Our final exam question.", []),
    (11, "still obeys only himself and remains as free as before", "question", None,
     "Is 'as free as before' the same freedom or a different kind?", [
         (None, "Different, I think. He says on p. 14 we swap natural liberty for civil liberty."),
     ]),
    (11, "There’s the basic problem that is solved by the social contract.", "note", None,
     "First use of 'social contract' in the book.", []),
    # ---- p. 12: total alienation and the general will (the crowded passage)
    (12, "of each associate, together with all his rights, to the whole community", "note", None,
     "Total alienation sounds terrifying. Give everything?", [
         (None, "(i)-(iii) are his three reasons it isn't."),
         (None, "Reason (ii) is the scary one: no rights held back, because there'd be no judge."),
     ]),
    (12, "Each man in giving himself to everyone gives himself to no-one", "note", None,
     "The key trick. Nobody in particular owns you.", []),
    (12, "Each man in giving himself to everyone gives himself to no-one", "note", "Jordan",
     "This is my favourite sentence so far.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", PROFESSOR, "First appearance of 'the general will' (Bennett's note says so). Everything after builds on it.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", None, "The contract in one sentence. Short enough to memorise.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", None, "'Supreme direction' is strong. The general will is the boss, not the government.", [
         (None, "And the government isn't even the sovereign. Sovereign = the people as a whole."),
     ]),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "question", None, "Is the general will just what the majority votes for?", [
         (None, "No, see Book 2 ch. 3 (p. 19): the will of all is not the general will."),
         (None, "But in practice how would you know the difference?"),
         (PROFESSOR, "That's the question for section on Thursday. Bring an example."),
     ]),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", "past", "We compared this to a group project where everyone's grade is the group's grade.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", None, "Connects back to the problem on p. 11: you obey the general will, which is partly yours.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", None, "Corporate capacity = acting as a member, not as an individual. That's the key.", []),
    (12, "Each of us puts his person and all his power in common under the supreme direction of the general will",
     "note", None, "Reminds me of Hobbes's Leviathan picture, a body made of people. But no king.", [
         (None, "Yes! 'moral and collective body' two lines down."),
     ]),
    (12, "we receive each member as an indivisible part of the whole", "note", None,
     "Indivisible part: you can't be partly in.", []),
    (12, "we receive each member as an indivisible part of the whole", "note", "past",
     "This line made our class argue about whether you can leave.", []),
    (12, "houses make a town, but citizens a city", "note", None, "Footnote gem. City as citizens, not buildings.", []),
    # ---- p. 13–14: the sovereign, forced to be free
    (13, "The sovereign, merely by virtue of what it is, is always what it ought to be.", "note", None,
     "This seems dangerous.", [
         (None, "It's true by definition though: if it stops aiming at the common good it isn't the sovereign."),
     ]),
    (13, "each individual as a man can have a particular will", "note", None,
     "Particular will vs general will inside one person. I want the free ride AND the society.", []),
    (14, "each individual will be forced to be free", "note", None, "The most controversial phrase in the book.", []),
    (14, "each individual will be forced to be free", "note", None,
     "This sounds like a dictatorship slogan.", [
         (None, "Read the next sentence: being made to obey the law protects you from 'personal dependence' "
                "on any one person."),
         (None, "Still creepy."),
         ("Jordan", "Both can be true. Berlin's 'Two Concepts of Liberty' is literally about this line."),
     ]),
    (14, "each individual will be forced to be free", "question", None,
     "Has anyone defended this line convincingly?", [
         (PROFESSOR, "Good one for an Ask: look for SEP's entry on Rousseau and the 'forced to be free' debate."),
     ]),
    (14, "each individual will be forced to be free", "note", "past", "Our TA: compare a law against drunk driving.", []),
    (14, "This is the key to the working of the political machine", "note", None,
     "Machine metaphor right after the body metaphor.", []),
    (14, "out of a dull and limited animal made a thinking being, a man", "note", None,
     "Society makes us human. Opposite of the noble savage reading people give him.", [
         (None, "But he also says 'if the abuses didn't pull him down'. He's hedging."),
     ]),
    (14, "civil liberty, which is limited by the general will", "note", "Jordan",
     "Natural liberty limited by strength, civil liberty by the general will. Trade-off table on this page.", []),
    # ---- p. 15–16: moral liberty, property
    (15, "obedience to a law that we prescribe to ourselves is liberty", "note", PROFESSOR,
     "Moral liberty. Compare Hobbes's 'absence of external obstacles'. Completely different idea of freedom.", []),
    (15, "obedience to a law that we prescribe to ourselves is liberty", "note", None, "Autonomy, literally self-law.", []),
    (15, "obedience to a law that we prescribe to ourselves is liberty", "note", None,
     "And then he says 'I have said too much about this'. Frustrating!", []),
    (15, "When Balboa stood on the sea-shore", "note", None,
     "Mocking claims of possession by ceremony. A dig at colonial land claims.", []),
    (16, "men who may be unequal in strength or intelligence become equal by agreement and legal right", "note", None,
     "Equality is made, not found. Opposite of Hobbes, who said we're naturally equal.", []),
    (16, "the social state is advantageous to men only when everyone has something and no-one has too much", "note", None,
     "Footnote 3 is radical. Economic inequality breaks the contract.", [
         (None, "Underrated footnote."),
     ]),
    # ---- p. 17–20: Book 2
    (17, "the power indeed may be transmitted, but not the will", "note", None,
     "You can hand over power but not your will. So no representatives for the sovereign.", []),
    (17, "the moment a master exists, there is no longer a sovereign", "note", None, "Strong.", []),
    (18, "the jugglers of Japan dismember a child", "note", None, "Weirdest image in the book.", []),
    (18, "the truth is no road to fortune", "note", None, "Shade at Grotius for flattering Louis XIII.", []),
    (19, "the general will is always in the right", "note", None, "'Always in the right' vs 'always right'. See translator's note.", [
         (None, "Bennett calls his own translation 'a cowardly compromise', which is great."),
     ]),
    (19, "The will of all is very different from the general will", "note", PROFESSOR,
     "The distinction to know for the exam. Will of all = sum of private interests. General will = the common interest.", []),
    (19, "The will of all is very different from the general will", "note", None,
     "Pluses and minuses cancel. Very math-y.", []),
    (19, "the populace is never corrupted, but it is often deceived", "note", None, "Misinformation, 1762 edition.", []),
    (19, "each citizen should think only his own thoughts", "note", None,
     "No parties. Would he hate group chats?", [
         (None, "He'd hate political parties more."),
     ]),
    (20, "the sovereign is sole judge of what is important", "note", None,
     "So who protects individuals? This is the worry about Rousseau and totalitarianism.", []),
    (20, "what makes the will general is less the number of voices than the common interest uniting them",
     "note", "Jordan", "Answers my question from p. 12: it's not just a vote count.", []),
]

# ---------- Week 3: Mill, On Liberty ch. I. An 1859 xerox with a previous reader's underlining.
MILL_PDF = SEED_DIR / "mill-on-liberty-ch1.pdf"
MILL_TITLE = "Week 3 · Mill, On Liberty, ch. I"
MILL_NOTES = [
    (17, "The object of this Essay is to assert one very simple principle", "note", PROFESSOR,
     "Heads up: this library copy has a previous reader's underlining on pp. 17–18, so the harm principle "
     "itself comes out garbled. Use Select area on it (charter rule 6).", []),
    (9, "the tyranny of the majority", "note", "Jordan",
     "Rousseau's general will vs Mill's tyranny of the majority. This is going to be a fight.", []),
    (1, "Civil, or Social Liberty", "note", None, "Not free will, political freedom. Glad he clarifies.", []),
]


def users():
    """(name, role, cohort) for this course, in log-in order: professor, featured students, the rest."""
    rows = [(PROFESSOR, "professor", CURRENT_COHORT)]
    rows += [(name, "student", CURRENT_COHORT) for name in FEATURED_STUDENTS + CLASSMATES]
    rows += [(name, "student", PAST_COHORT) for name in PAST_STUDENTS]
    return rows


def add_course(conn, uploads_dir):
    """The course, its people, charter and proposals, its three readings and every note above."""
    course_id = conn.execute("INSERT INTO course (title, current_cohort) VALUES (?, ?)",
                             (COURSE_TITLE, CURRENT_COHORT)).lastrowid
    conn.executemany("INSERT INTO users (name, role, cohort, course_id) VALUES (?, ?, ?, ?)",
                     [(*u, course_id) for u in users()])
    conn.execute(
        """INSERT INTO charter (course_id, text_md, permissible_sources, max_explanation_words, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (course_id, CHARTER_TEXT, PERMISSIBLE_SOURCES, MAX_EXPLANATION_WORDS, db.now()),
    )
    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM users WHERE course_id = ?", (course_id,))}
    add_charter_comments(conn, course_id, ids, CHARTER_COMMENTS, days_ago(18), days_ago(1))
    # Maya never writes: she isn't in the rota.
    rota = Rota(ids, CLASSMATES, PAST_STUDENTS)
    prof = ids[PROFESSOR]

    locke_id, locke_pdf = add_reading(conn, course_id, LOCKE_TITLE, LOCKE_PDF, uploads_dir, prof, days_ago(16))
    add_notes(conn, locke_id, locke_pdf, LOCKE_NOTES, rota, days_ago(15), days_ago(8))
    rousseau_id, rousseau_pdf = add_reading(conn, course_id, ROUSSEAU_TITLE, ROUSSEAU_PDF, uploads_dir, prof, days_ago(8))
    add_notes(conn, rousseau_id, rousseau_pdf, ROUSSEAU_NOTES, rota, days_ago(7), days_ago(0.1))
    mill_id, mill_pdf = add_reading(conn, course_id, MILL_TITLE, MILL_PDF, uploads_dir, prof, days_ago(1.5))
    add_notes(conn, mill_id, mill_pdf, MILL_NOTES, rota, days_ago(1.4), days_ago(0.2))
    return course_id
