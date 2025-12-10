--
-- PostgreSQL database dump
--

\restrict ZwwVz4xg3ibUmTTGuARWzKt6Vhc3SnLglfkP0xiZqVmyoOXvv4dFpeWjo1GyXVK

-- Dumped from database version 15.15 (Debian 15.15-1.pgdg13+1)
-- Dumped by pg_dump version 15.15 (Debian 15.15-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: robot_movement; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.robot_movement (
    "time" timestamp with time zone NOT NULL,
    robot_id integer NOT NULL,
    x double precision,
    y double precision,
    ori double precision,
    distance double precision DEFAULT 0
);


ALTER TABLE public.robot_movement OWNER TO postgres;

--
-- Name: robot_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.robot_sessions (
    id integer NOT NULL,
    robot_id integer,
    status character varying(20),
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    session_duration interval
);


ALTER TABLE public.robot_sessions OWNER TO postgres;

--
-- Name: robot_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.robot_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.robot_sessions_id_seq OWNER TO postgres;

--
-- Name: robot_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.robot_sessions_id_seq OWNED BY public.robot_sessions.id;


--
-- Name: robots; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.robots (
    id integer NOT NULL,
    name text NOT NULL,
    model text,
    mongodb_id text,
    nickname text,
    status text DEFAULT 'idle'::text,
    last_poi text,
    sn text,
    ip text,
    time_created timestamp with time zone DEFAULT now()
);


ALTER TABLE public.robots OWNER TO postgres;

--
-- Name: robots_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.robots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.robots_id_seq OWNER TO postgres;

--
-- Name: robots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.robots_id_seq OWNED BY public.robots.id;


--
-- Name: tasks_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tasks_history (
    id integer NOT NULL,
    task_id bigint NOT NULL,
    robot_id integer NOT NULL,
    last_poi text NOT NULL,
    target_poi text NOT NULL,
    status text NOT NULL,
    distance double precision NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    notes text
);


ALTER TABLE public.tasks_history OWNER TO postgres;

--
-- Name: tasks_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tasks_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tasks_history_id_seq OWNER TO postgres;

--
-- Name: tasks_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tasks_history_id_seq OWNED BY public.tasks_history.id;


--
-- Name: robot_sessions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robot_sessions ALTER COLUMN id SET DEFAULT nextval('public.robot_sessions_id_seq'::regclass);


--
-- Name: robots id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robots ALTER COLUMN id SET DEFAULT nextval('public.robots_id_seq'::regclass);


--
-- Name: tasks_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks_history ALTER COLUMN id SET DEFAULT nextval('public.tasks_history_id_seq'::regclass);


--
-- Data for Name: robot_movement; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.robot_movement ("time", robot_id, x, y, ori, distance) FROM stdin;
\.


--
-- Data for Name: robot_sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.robot_sessions (id, robot_id, status, "timestamp", session_duration) FROM stdin;
\.


--
-- Data for Name: robots; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.robots (id, name, model, mongodb_id, nickname, status, last_poi, sn, ip, time_created) FROM stdin;
1	Kennon S100	AMR	\N	Kennon 1	idle		4323432535	192.168.0.43	2025-12-10 02:27:55.97844+00
2	Fielder Robot	AMR	\N	Fielder 1	idle		2682406203417T7	192.168.0.47	2025-12-10 02:27:55.97844+00
\.


--
-- Data for Name: tasks_history; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tasks_history (id, task_id, robot_id, last_poi, target_poi, status, distance, start_time, end_time, notes) FROM stdin;
\.


--
-- Name: robot_sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.robot_sessions_id_seq', 1, false);


--
-- Name: robots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.robots_id_seq', 2, true);


--
-- Name: tasks_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tasks_history_id_seq', 1, false);


--
-- Name: robot_movement robot_movement_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robot_movement
    ADD CONSTRAINT robot_movement_pkey PRIMARY KEY ("time", robot_id);


--
-- Name: robot_sessions robot_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robot_sessions
    ADD CONSTRAINT robot_sessions_pkey PRIMARY KEY (id);


--
-- Name: robots robots_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robots
    ADD CONSTRAINT robots_pkey PRIMARY KEY (id);


--
-- Name: tasks_history tasks_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks_history
    ADD CONSTRAINT tasks_history_pkey PRIMARY KEY (id);


--
-- Name: idx_robot_sessions_robot; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_robot_sessions_robot ON public.robot_sessions USING btree (robot_id);


--
-- Name: idx_robot_sessions_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_robot_sessions_time ON public.robot_sessions USING btree ("timestamp");


--
-- Name: robot_sessions robot_sessions_robot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.robot_sessions
    ADD CONSTRAINT robot_sessions_robot_id_fkey FOREIGN KEY (robot_id) REFERENCES public.robots(id);


--
-- Name: tasks_history tasks_history_robot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tasks_history
    ADD CONSTRAINT tasks_history_robot_id_fkey FOREIGN KEY (robot_id) REFERENCES public.robots(id);


--
-- PostgreSQL database dump complete
--

\unrestrict ZwwVz4xg3ibUmTTGuARWzKt6Vhc3SnLglfkP0xiZqVmyoOXvv4dFpeWjo1GyXVK

