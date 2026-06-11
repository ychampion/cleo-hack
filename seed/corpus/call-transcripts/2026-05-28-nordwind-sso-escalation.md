# Call — Nordwind Labs: Okta SSO escalation

Date: 2026-05-28
Account: Nordwind Labs
Participants: Maya Chen (Lumen), Jonah Park (Lumen), Erik Sandstrom (Nordwind Labs), Anders Bell (Nordwind Labs)

---

**Maya Chen (Lumen):** Thanks for making time, both. We know the SSO setup has been painful and we want to get to the bottom of it today.

**Erik Sandstrom (Nordwind Labs):** Appreciate it. To set the stakes plainly: we picked Lumen over two competitors in April. The one hard requirement from our security team was Okta SSO, and a week into rollout it still doesn't work. I'm fielding questions internally about whether we picked the wrong vendor.

**Anders Bell (Nordwind Labs):** Technically, here's what happens. We upload the Okta IdP metadata XML in your admin panel and it rejects it with "invalid certificate chain". We rotated our signing cert in May, so the metadata now includes an intermediate certificate. My strong suspicion is your parser only validates a single leaf cert and chokes on the chain.

**Jonah Park (Lumen):** That matches two other reports we've had. Did you try stripping the intermediate cert out of the XML?

**Anders Bell (Nordwind Labs):** We did, as a hack — then the upload succeeds but the actual SAML handshake fails at login with a signature mismatch, which makes sense because Okta signs with the full chain. So the workaround is a dead end. We need the parser to accept a chain, that's table stakes for any enterprise IdP setup.

**Erik Sandstrom (Nordwind Labs):** And on timeline — our rollout window with IT closes June 13. If 180 people can't log in via Okta by then, the project pauses until Q4 and procurement re-opens the vendor evaluation. That's not a threat, it's just how our process works.

**Maya Chen (Lumen):** Understood. We're treating this as our top enterprise issue. While we're here — any other blockers for the rollout?

**Anders Bell (Nordwind Labs):** Two smaller things. Provisioning: we'd want SCIM eventually, but honestly even the manual invite flow is confusing — I had to dig through Settings to find where members get added, and there's no way to invite a whole group at once.

**Erik Sandstrom (Nordwind Labs):** Also our data platform team asked whether you have outbound webhooks. We'd like login and metric events flowing into our SIEM and warehouse. Not a blocker like SSO, but it came up in the security review.

**Jonah Park (Lumen):** Noted, both are on the list. Anything you like so far, so we keep it intact?

**Erik Sandstrom (Nordwind Labs):** The product itself, genuinely. The pilot team's leads say the cycle-time dashboard already changed two standup conversations. That's why I'm still on this call instead of signing with the runner-up.
