package com.example.orders.architecture;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

/**
 * Boundary-rule definitions for this fixture.
 *
 * agent-redline treats these as red-zone files: weakening or removing a
 * rule requires explicit architecture-review. Don't edit without a
 * checkpoint.
 */
@AnalyzeClasses(
    packages = "com.example.orders",
    importOptions = ImportOption.DoNotIncludeTests.class
)
class DependencyArchitectureTest {

    @ArchTest
    static final ArchRule domain_must_not_depend_on_adapters =
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..");

    @ArchTest
    static final ArchRule application_must_not_depend_on_persistence_adapters =
        noClasses()
            .that().resideInAPackage("..application..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..persistence..");

    @ArchTest
    static final ArchRule controllers_must_not_access_repositories_directly =
        noClasses()
            .that().resideInAPackage("..controller..")
            .should().dependOnClassesThat()
            .resideInAnyPackage("..adapter..persistence..");
}
