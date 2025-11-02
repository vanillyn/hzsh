NAME = "hazel / shell"

GUILD_ID = 1429674770596761685
NEO_POLITA = 1395939916189405325

SHELL_ACCESS_ROLE = "> connected..."
ACHIEVEMENTS_CHANNEL = 1429897092226351244

VERSION = "1.3"

USERMOD_MAPPINGS = {
    "pronouns": {
        "he": "he / him",
        "him": "he / him",
        "he/him": "he / him",
        "masc": "he / him",
        "masculine": "he / him",
        
        "she": "she / her",
        "her": "she / her",
        "she/her": "she / her",
        "fem": "she / her",
        "feminine": "she / her",
        
        "they": "they / them",
        "them": "they / them",
        "they/them": "they / them",
        
        "it": "it / its",
        "its": "it / its",
        "it/its": "it / its",
        
        "other": "/ other",
        
        "ask": "ask / me",
        "askme": "ask / me",
    },
    
    "proficiency": {
        "new": "\\ new to computer science",
        "newcs": "\\ new to computer science",
        "beginner": "\\ new to computer science",
        "computerscience": "\\ new to computer science",
        
        "newlinux": "\\ new to linux",
        "linux": "\\ new to linux",
        "linuxnew": "\\ new to linux",
    },
    
    "os": {
        "windows": "\\ windows",
        "win": "\\ windows",
        
        "windowsxp": "\\ windows xp",
        "xp": "\\ windows xp",
        
        "windows7": "\\ windows 7",
        "win7": "\\ windows 7",
        
        "windowsnt": "\\ windows (pre-nt)",
        "prent": "\\ windows (pre-nt)",
        "oldwindows": "\\ windows (pre-nt)",
        "win95": "\\ windows (pre-nt)",
        "win98": "\\ windows (pre-nt)",
        
        "macos": "\\ macos",
        "mac": "\\ macos",
        "osx": "\\ macos",
        "darwin": "\\ macos",
        
        "bsd": "\\ berkeley software distribution",
        "freebsd": "\\ berkeley software distribution",
        "openbsd": "\\ berkeley software distribution",
        "netbsd": "\\ berkeley software distribution",
        "berkeley": "\\ berkeley software distribution",
        
        "arch": "\\ arch linux",
        "archlinux": "\\ arch linux",
        "btw": "\\ arch linux",
        
        "ubuntu": "\\ ubuntu",
        
        "gentoo": "\\ gentoo",
        
        "fedora": "\\ fedora",
        "rhel": "\\ fedora",
        
        "nixos": "\\ nixos",
        "nix": "\\ nixos",
        
        "debian": "\\ debian",
        "deb": "\\ debian",
        
        "void": "\\ void",
        "voidlinux": "\\ void",
        
        "redhat": "\\ red hat",
        
        "popos": "\\ pop! os",
        "pop": "\\ pop! os",
        
        "haiku": "\\ haiku",
        
        "solaris": "\\ solaris",
        
        "centos": "\\ centos",
        
        "bedrock": "\\ bedrock",
        
        "alpine": "\\ alpine",
        
        "steamos": "\\ steamos",
        "steam": "\\ steamos",
        
        "fromscratch": "\\ from scratch",
        "lfs": "\\ from scratch",
        
        "slackware": "\\ slackware",
        "slack": "\\ slackware",
        
        "chromeos": "\\ chromeos",
        "chrome": "\\ chromeos",
        
        "aix": "\\ aix",
        
        "plan9": "\\ plan9",
    },
    
    "ping": {
        "technews": "+ tech news",
        "news": "+ tech news",
        
        "support": "+ ping for support",
        "help": "+ ping for support",
        
        "announcements": "+ announcements",
        "announce": "+ announcements",
    },
    
    "channel": {
        "controversial": "+ controversial",
        "politics": "+ controversial",
    }
}

USERMOD_CATEGORIES = {
    "pronouns": "pronouns",
    "proficiency": "proficiency level",
    "os": "operating system",
    "ping": "ping preferences",
    "channel": "extra channel access",
}

ACHIEVEMENTS = {
    "echo": {
        "name": "hello hello hello hello world world world world world",
        "description": "run the echo command",
        "rarity": "common",
        "trigger_type": "command",
        "trigger_value": "echo",
        "role": None,
    },
    "imtrapped": {
        "name": "i don't know how to exit...",
        "description": "run the wrong exit command",
        "rarity": "common",
        "trigger_type": "command",
        "trigger_value": "exit",
        "role": None,
    },
    "crash": {
        "name": "crash!",
        "description": "run an existing command that gives a non-zero exit code.",
        "rarity": "rare",
        "trigger_type": "nonzero_exit",
        "trigger_value": None,
        "role": "> bot breaker",
    },
    "central": {
        "name": "...",
        "description": "find a secret file in a familiar directory.",
        "rarity": "master",
        "trigger_type": "file_read",
        "trigger_value": "/.c/n/s",
        "role": "> perceptive",
    },
    "neopolita": {
        "name": "neo / polita",
        "description": "be a member of both hazel / run and neo * polita",
        "rarity": "rare",
        "trigger_type": "mutual_servers",
        "trigger_value": None,
        "role": "> neo / polita",
    },
    "ricer": {
        "name": "ricer instinct",
        "description": "run hazelfetch",
        "rarity": "rare",
        "trigger_type": "message_count",
        "trigger_value": (">hazelfetch", 1),
        "role": "> ricer instinct",
    },
    "packaged": {
        "name": "packaged",
        "description": "run the pacman package manager",
        "rarity": "common",
        "trigger_type": "command",
        "trigger_value": "pacman",
        "role": "> packaged",
    },
    "meow": {
        "name": "meow :3",
        "description": "send 20 messages containing the word meow",
        "rarity": "common",
        "trigger_type": "message_count",
        "trigger_value": ("meow", 20),
        "role": "> meow :3",
    },
    "meowmeow": {
        "name": "meow meow :3 :3",
        "description": "send 100 messages containing the word meow. i like cats too :3",
        "rarity": "rare",
        "trigger_type": "message_count",
        "trigger_value": ("meow", 100),
        "role": None,
    },
    "supermeow": {
        "name": "super meow... :3 :3 :3",
        "description": "send 500 messages containing the word meow. a true cat enthusiast.",
        "rarity": "rare",
        "trigger_type": "message_count",
        "trigger_value": ("meow", 500),
        "role": None,
    },
    "literallyobsessive": {
        "name": "literally obsessive...",
        "description": "send 1,000 messages containing the word meow. this user really loves cats.",
        "rarity": "legendary",
        "trigger_type": "message_count",
        "trigger_value": ("meow", 1000),
        "role": None,
    },
    "theendofallmeows": {
        "name": "the end of all meows... :3",
        "description": "send 100,000 messages containing the word meow. this user is probably a cat.",
        "rarity": "master",
        "trigger_type": "message_count",
        "trigger_value": ("meow", 100000),
        "role": None,
    },
    "whatdidyousay": {
        "name": "what did you say?",
        "description": "send 20 messages containing the word woof",
        "rarity": "common",
        "trigger_type": "message_count",
        "trigger_value": ("woof", 20),
        "role": "> woof :3",
    },
    "saythatagain": {
        "name": "say that again...",
        "description": "send 100 messages containing the word woof",
        "rarity": "rare",
        "trigger_type": "message_count",
        "trigger_value": ("woof", 100),
        "role": "> got that dawg",
    },
    "suchadog": {
        "name": "such a dog...",
        "description": "send 500 messages containing the word woof",
        "rarity": "legendary",
        "trigger_type": "message_count",
        "trigger_value": ("woof", 500),
        "role": None,
    },
    "yourewhat": {
        "name": "you're what?",
        "description": "say \"i'm confused\" five times",
        "rarity": "common",
        "trigger_type": "message_count",
        "trigger_value": ("i'm confused", 5),
        "role": "> a_confuseduser",
    },
    "toroplushie": {
        "name": ":toroplushie:",
        "description": "use the :toroplushie: emote 20 times",
        "rarity": "rare",
        "trigger_type": "message_count",
        "trigger_value": (":toroplushie:", 20),
        "role": "> XD",
    },
    "lost": {
        "name": "lost...",
        "description": "you're late, but you can still bring us silence.",
        "rarity": "master",
        "trigger_type": "message_count",
        "trigger_value": ("forest", 20),
        "role": "> lost...",
    },
    "thestart": {
        "name": "the start",
        "description": "run a hzsh session for the first time",
        "rarity": "common",
        "trigger_type": "first_hzsh",
        "trigger_value": None,
        "role": "> the start",
    },
    "gaming": {
        "name": "we should play sometime...",
        "description": "play R.E.P.O., Minecraft, or THE FINALS",
        "rarity": "rare",
        "trigger_type": "presence",
        "trigger_value": ["R.E.P.O.", "Minecraft", "THE FINALS"],
        "role": "> we should play sometime...",
    },
    "elitegamer": {
        "name": "elite gamer",
        "description": "have 100+ games on a linked public Steam profile",
        "rarity": "legendary",
        "trigger_type": "steam_games",
        "trigger_value": 100,
        "role": "> elite gamer",
    },
    "blocky": {
        "name": "blocky",
        "description": "run minecraft, prismlauncher, or multimc in hzsh",
        "rarity": "common",
        "trigger_type": "command",
        "trigger_value": ["minecraft", "prismlauncher", "multimc"],
        "role": "> blocky",
    },
    "sudoers": {
        "name": "sudoers",
        "description": "run sudo -i, doas -s, or su in hzsh",
        "rarity": "rare",
        "trigger_type": "command",
        "trigger_value": ["sudo -i", "doas -s", "su"],
        "role": "> sudoers",
    },
    "baller": {
        "name": "baller",
        "description": "solve the hzconnect puzzle",
        "rarity": "legendary",
        "trigger_type": "puzzle",
        "trigger_value": None,
        "role": "> baller",
    }
}

RARITY_XP = {
    "common": 25,
    "rare": 50,
    "legendary": 100,
    "master": 1000,
}

ACHIEVEMENT_MILESTONES = {
    5: "$ navigating... [5]",
    10: "$ mastering... [10]",
    50: "$ réseau noisette [50]",
}