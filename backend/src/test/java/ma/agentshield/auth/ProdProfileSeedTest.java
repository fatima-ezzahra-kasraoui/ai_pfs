package ma.agentshield.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;
import ma.agentshield.support.PostgresTestConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Hors profil dev, AUCUN compte n'est cree, meme si DEV_SEED_PASSWORD est defini. */
@SpringBootTest
@Import(PostgresTestConfig.class)
@ActiveProfiles("prod")
class ProdProfileSeedTest {

    @DynamicPropertySource
    static void seed(DynamicPropertyRegistry registry) {
        registry.add("agentshield.dev-seed.password", () -> "seed-" + UUID.randomUUID());
    }

    @Autowired
    private UserAccountRepository users;

    @Test
    void noSeedAccountInProd() {
        assertThat(users.count()).isZero();
    }
}
