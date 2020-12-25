create table if not exists accounts (
    twitch_userid integer,
    twitch_username text,
    discord_id integer,
    id integer primary key,
    points integer default 0,
    hours integer default 0,
    editor integer default 0,
    badges text
);
create table if not exists quotes (
    quote text,
    insert_time integer primary key
);
create table if not exists commands (
    name text primary key,
    places integer not null,
    message text not null,
    cooldown integer,
    limits text,
    isscript integer
);
create table if not exists strikes (
    user_id integer primary key,
    amount integer
);
create table if not exists mod_cases(
    user_id integer,
    mod_id integer,
    reason text
);
create table if not exists timers (
    id integer primary key autoincrement,
    timer_type text not null,
    fire_at integer not null,
    payload blob
);
create table if not exists automod_words (
    word text primary key,
    is_twitch integer,
    is_discord integer
);
create table if not exists automod_domains (
    domain text primary key
);
create table if not exists chat_timers (
    name text primary key,
    delay integer not null default 60,
    minlines integer default 20,
    place integer not null default 2,
    shared integer default 0,
    content text not null,
    channel integer,
    loop text
);
create table if not exists chat_timer_loops (
    name text primary key,
    delay integer not null,
    minlines integer,
    place integer not null default 2,
    channel integer
);
create table if not exists scripts (
    identifier text not null primary key,
    scriptname text not null,
    state integer not null default 0
);