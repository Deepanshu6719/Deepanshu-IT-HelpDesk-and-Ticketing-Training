# Module 16 — Final Project Checkpoint

## Project

IT Helpdesk and Ticketing System

## Objective

Review the implementation delivered through Modules 1–15, identify remaining functional and security gaps, verify existing functionality and prepare the application for final delivery.

## Checkpoint 1 — Data Model & Authentication

### Domain Adaptation

The reference TaskFlow project has been adapted to the Helpdesk domain.

| Reference entity | Helpdesk equivalent |
|---|---|
| User | User |
| Container / Project | Department |
| Membership / ProjectMember | User.department_id |
