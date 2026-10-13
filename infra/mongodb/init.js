db = db.getSiblingDB("work_order_db");
db.createUser({
  user: "work_order_user",
  pwd: "work_order_pass",
  roles: [{ role: "readWrite", db: "work_order_db" }]
});

db = db.getSiblingDB("notification_db");
db.createUser({
  user: "notification_user",
  pwd: "notification_pass",
  roles: [{ role: "readWrite", db: "notification_db" }]
});
