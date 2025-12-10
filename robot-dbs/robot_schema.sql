CREATE TABLE public.robots (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    model        TEXT,
    mongodb_id   TEXT,
    nickname     TEXT,
    status       TEXT DEFAULT 'idle',
    last_poi     TEXT,
    sn           TEXT,
    ip           TEXT,
    time_created TIMESTAMPTZ DEFAULT now()
);

INSERT INTO public.robots 
    (id, name, model, mongodb_id, nickname, status, last_poi, sn, ip, time_created)
VALUES
    (1, 'Kennon S100', 'AMR', NULL, 'Kennon 1', 'idle', '', '4323432535', '192.168.0.43', now()),
    (2, 'Fielder Robot', 'AMR', NULL, 'Fielder 1', 'idle', '', '2682406203417T7', '192.168.0.47', now());

SELECT setval(pg_get_serial_sequence('public.robots','id'), (SELECT MAX(id) FROM robots));

CREATE TABLE public.robot_sessions (
    id               SERIAL PRIMARY KEY,
    robot_id         INTEGER REFERENCES robots(id),
    status           VARCHAR(20),
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_duration INTERVAL
);

CREATE INDEX idx_robot_sessions_robot ON robot_sessions(robot_id);
CREATE INDEX idx_robot_sessions_time ON robot_sessions(timestamp);

CREATE TABLE public.robot_movement (
    time     TIMESTAMPTZ NOT NULL,
    robot_id INTEGER NOT NULL,
    x        DOUBLE PRECISION,
    y        DOUBLE PRECISION,
    ori      DOUBLE PRECISION,
    distance DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (time, robot_id)
);

CREATE TABLE public.tasks_history (
    id         SERIAL PRIMARY KEY,
    task_id    BIGINT NOT NULL,
    robot_id   INTEGER NOT NULL REFERENCES robots(id),
    last_poi   TEXT NOT NULL,
    target_poi TEXT NOT NULL,
    status     TEXT NOT NULL,
    distance   DOUBLE PRECISION NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time   TIMESTAMP NOT NULL,
    notes      TEXT
);
