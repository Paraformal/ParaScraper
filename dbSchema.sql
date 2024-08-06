-- Create the database
CREATE DATABASE IF NOT EXISTS lebanese_rulings;
USE lebanese_rulings;

-- Create the courts table
CREATE TABLE courts (
    court_id INT AUTO_INCREMENT PRIMARY KEY,
    court_name VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- Create the judges table
CREATE TABLE judges (
    judge_id INT AUTO_INCREMENT PRIMARY KEY,
    judge_name VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

-- Create the rulings table
CREATE TABLE rulings (
    ruling_id INT AUTO_INCREMENT PRIMARY KEY,
    court_id INT,
    ruling_number VARCHAR(255) NOT NULL,
    year INT NOT NULL,
    date DATE,
    president_id INT,
    full_text TEXT,
    FOREIGN KEY (court_id) REFERENCES courts(court_id),
    FOREIGN KEY (president_id) REFERENCES judges(judge_id)
) ENGINE=InnoDB;

-- Create the ruling_members table
CREATE TABLE ruling_members (
    ruling_id INT,
    judge_id INT,
    role VARCHAR(255),
    FOREIGN KEY (ruling_id) REFERENCES rulings(ruling_id),
    FOREIGN KEY (judge_id) REFERENCES judges(judge_id),
    PRIMARY KEY (ruling_id, judge_id)
) ENGINE=InnoDB;

-- Create indexes to improve query performance
CREATE INDEX idx_ruling_number ON rulings(ruling_number);
CREATE INDEX idx_year ON rulings(year);
CREATE INDEX idx_date ON rulings(date);
